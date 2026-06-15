import time
import math
import sqlite3
import json
import uuid
import os
from typing import Dict, Any, Optional
from core.state_manager import StateManager, SystemState

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "falldetection.db")

class DecisionEngine:
    """
    Multimodal sensor fusion engine (spec §9).
    Uses a weighted scoring model to evaluate fall probability
    and combines CV, motion, vitals, and audio data streams.
    """
    
    # Weighted scoring coefficients (spec §9)
    W_CV = 0.4
    W_MOTION = 0.3
    W_INACTIVITY = 0.2
    W_AUDIO = 0.1
    
    def __init__(self, patient_id: str):
        self.patient_id = patient_id
        self.state_manager = StateManager(patient_id)
        
        # ── Tracking timestamps ──
        self.last_cv_fall_time = 0.0
        self.last_cv_confidence = 0.0
        self.last_accel_spike_time = 0.0
        self.last_audio_distress_time = 0.0
        self.last_movement_time = time.time()
        self.hardware_confirmed_fall = False
        
        # ── Context-aware visibility (spec §8) ──
        self.is_person_visible = False
        
        # ── Latest sensor readings (cached for dashboard) ──
        self.latest_vitals = {"heart_rate": 75, "spo2": 98}
        self.latest_motion = {"ax": 0.0, "ay": 0.0, "az": 0.0, "smv": 1.0, "gyro": 0.0}
        self.latest_audio = {"distress_sound_detected": False}
        self.latest_fall_score = 0.0
        
        # ── Vitals connected flag (only evaluate vitals rules when real data received) ──
        self.vitals_connected = False
        
        # ── CV Fall Debounce (require N events in window to prevent single-frame glitches) ──
        self.cv_fall_event_times = []  # timestamps of recent CV fall events
        self.CV_DEBOUNCE_COUNT = 3     # need 3 CV fall events
        self.CV_DEBOUNCE_WINDOW = 2.0  # within 2 seconds
        
        # ── Configuration thresholds ──
        self.TIME_SYNC_WINDOW = 3.0       # seconds between CV and Accel events
        self.INACTIVITY_TIMEOUT = 10.0    # seconds of no movement to confirm fall
        self.FALL_SCORE_THRESHOLD = 0.55  # weighted score to confirm fall
        self.SMV_SPIKE_THRESHOLD = 2.5    # signal magnitude vector spike threshold (spec §6)
        self.CRITICAL_HR_HIGH = 120
        self.CRITICAL_HR_LOW = 45
        self.CRITICAL_SPO2 = 92
        
        # ── Event history for dashboard ──
        self.event_history = self._load_recent_history()
        
    def _load_recent_history(self) -> list:
        """Load last 100 events from SQLite to prepopulate dashboard."""
        history = []
        try:
            if not os.path.exists(DB_FILE):
                return history
                
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Fetch last 100 events for this patient, oldest first (ascending by time)
            cursor.execute('''
                SELECT * FROM (
                    SELECT time, event_type, confidence, metadata, 'UNKNOWN' as system_state
                    FROM event_log
                    WHERE patient_id = ?
                    ORDER BY time DESC
                    LIMIT 100
                ) sub
                ORDER BY sub.time ASC
            ''', (self.patient_id,))
            
            rows = cursor.fetchall()
            for row in rows:
                meta = row["metadata"]
                if meta:
                    try:
                        meta = json.loads(meta)
                    except json.JSONDecodeError:
                        meta = {}
                else:
                    meta = {}
                    
                history.append({
                    "timestamp": row["time"],
                    "event_type": row["event_type"],
                    "confidence": row["confidence"],
                    "metadata": meta,
                    "system_state": row["system_state"], # Approximated as DB doesn't store state on every log natively before
                })
            conn.close()
        except Exception as e:
            print(f"Error loading history from DB: {e}")
        return history
        
    # ──────────────────────────────────────────────
    # SMV Calculation (spec §6)
    # ──────────────────────────────────────────────
    @staticmethod
    def compute_smv(ax: float, ay: float, az: float) -> float:
        """Signal Magnitude Vector = sqrt(ax² + ay² + az²)"""
        return math.sqrt(ax**2 + ay**2 + az**2)

    def reset_history(self):
        """Clear recent event timestamps to prevent immediate re-triggering after manual reset."""
        self.last_cv_fall_time = 0.0
        self.last_accel_spike_time = 0.0
        self.last_audio_distress_time = 0.0
        self.hardware_confirmed_fall = False
        self.latest_fall_score = 0.0
        
    # ──────────────────────────────────────────────
    # Event Processors
    # ──────────────────────────────────────────────
    def process_cv_event(self, event: Dict[str, Any]) -> str:
        """Process incoming Computer Vision event."""
        current_time = time.time()
        
        self.is_person_visible = event.get("person_visible", False)
        fall_predicted = event.get("fall_predicted", False)
        confidence = event.get("confidence", 0.0)
        
        if fall_predicted:
            self.last_cv_fall_time = current_time
            self.last_cv_confidence = confidence
            
            # Debounce: track timestamps of CV fall events
            self.cv_fall_event_times.append(current_time)
            # Only keep events within the debounce window
            self.cv_fall_event_times = [t for t in self.cv_fall_event_times 
                                        if (current_time - t) < self.CV_DEBOUNCE_WINDOW]
            
            if len(self.cv_fall_event_times) >= self.CV_DEBOUNCE_COUNT:
                self._log_event("CV_FALL_PREDICTED", confidence, event)
            # else: too few events, don't log yet (noise filtering)
            
        return self._evaluate_fusion_rules(current_time)

    def process_iot_event(self, event: Dict[str, Any]) -> str:
        """Process incoming Wearable/IoT event (motion + vitals + audio combined)."""
        current_time = time.time()
        
        # ── Motion with SMV (spec §6) ──
        ax = event.get("ax", 0.0)
        ay = event.get("ay", 0.0)
        az = event.get("az", 0.0)
        gyro = event.get("gyro", 0.0)
        smv = self.compute_smv(ax, ay, az)
        
        self.latest_motion = {"ax": ax, "ay": ay, "az": az, "smv": round(smv, 3), "gyro": gyro}
        
        if smv > self.SMV_SPIKE_THRESHOLD:
            self.last_accel_spike_time = current_time
            self._log_event("MOTION_SPIKE", smv, {"smv": smv, "ax": ax, "ay": ay, "az": az})
        if event.get("motion") == "sudden":
            self.last_accel_spike_time = current_time
            self.hardware_confirmed_fall = True
        
        # Normal movement resets inactivity timer
        # > 1.2G or < 0.8G indicates movement, preventing the timer from advancing.
        if smv > 1.2 or smv < 0.8:
            self.last_movement_time = current_time
            
        # ── Vitals ──
        hr = event.get("heart_rate")
        spo2 = event.get("spo2")
        if hr is not None:
            self.latest_vitals["heart_rate"] = hr
            if hr != 75:  # Not the default placeholder
                self.vitals_connected = True
        if spo2 is not None:
            self.latest_vitals["spo2"] = spo2
            if spo2 != 98:  # Not the default placeholder
                self.vitals_connected = True
        
        # ── Audio ──
        if event.get("distress_sound_detected", False):
            self.last_audio_distress_time = current_time
            self.latest_audio["distress_sound_detected"] = True
            self._log_event("AUDIO_DISTRESS", 1.0, event)
        else:
            self.latest_audio["distress_sound_detected"] = False
            
        return self._evaluate_fusion_rules(current_time)
        
    # ──────────────────────────────────────────────
    # Weighted Scoring Model (spec §9)
    # ──────────────────────────────────────────────
    def _compute_fall_score(self, current_time: float) -> float:
        """
        Fall Score = 0.4 × CV confidence + 0.3 × motion spike + 0.2 × inactivity + 0.1 × audio
        """
        # CV component: recent fall prediction confidence
        cv_recency = max(0, 1.0 - (current_time - self.last_cv_fall_time) / self.TIME_SYNC_WINDOW)
        cv_score = self.last_cv_confidence * cv_recency
        
        # Motion spike component: binary, recent
        motion_recency = max(0, 1.0 - (current_time - self.last_accel_spike_time) / self.TIME_SYNC_WINDOW)
        motion_score = 1.0 * motion_recency
        
        # Inactivity component: how long since last movement (normalized)
        inactivity_duration = current_time - self.last_movement_time
        inactivity_score = min(1.0, inactivity_duration / self.INACTIVITY_TIMEOUT)
        
        # Audio distress component: recent
        audio_recency = max(0, 1.0 - (current_time - self.last_audio_distress_time) / 5.0)
        audio_score = 1.0 * audio_recency
        
        fall_score = (
            self.W_CV * cv_score +
            self.W_MOTION * motion_score +
            self.W_INACTIVITY * inactivity_score +
            self.W_AUDIO * audio_score
        )
        
        self.latest_fall_score = round(fall_score, 3)
        return fall_score
        
    # ──────────────────────────────────────────────
    # Fusion Rules (spec §8, §9, §10)
    # ──────────────────────────────────────────────
    def _evaluate_fusion_rules(self, current_time: float) -> str:
        """Core fusion logic combining all modalities."""
        current_state = self.state_manager.state
        hr = self.latest_vitals["heart_rate"]
        spo2 = self.latest_vitals["spo2"]
        
        fall_score = self._compute_fall_score(current_time)
        
        # ── Rule 1: NORMAL → POSSIBLE_FALL ──
        if current_state == SystemState.NORMAL:
            cv_recent = (current_time - self.last_cv_fall_time) < 2.0
            accel_recent = (current_time - self.last_accel_spike_time) < 2.0
            
            if self.hardware_confirmed_fall:
                self.state_manager.transition_to(
                    SystemState.FALL_CONFIRMED,
                    "ESP32 Advanced Hardware State Machine Confirmed Fall"
                )
                self.hardware_confirmed_fall = False
                current_state = SystemState.FALL_CONFIRMED
            elif cv_recent and len(self.cv_fall_event_times) >= self.CV_DEBOUNCE_COUNT:
                # Only transition if we have enough debounced CV events
                self.state_manager.transition_to(
                    SystemState.POSSIBLE_FALL, 
                    f"CV fall debounced ({len(self.cv_fall_event_times)} events, score={fall_score:.2f})"
                )
                current_state = SystemState.POSSIBLE_FALL
            elif accel_recent:
                self.state_manager.transition_to(
                    SystemState.POSSIBLE_FALL, 
                    f"Accel spike detected (score={fall_score:.2f})"
                )
                current_state = SystemState.POSSIBLE_FALL
                
        # ── Hardware Override ──
        if current_state == SystemState.POSSIBLE_FALL and getattr(self, 'hardware_confirmed_fall', False):
            self.state_manager.transition_to(
                SystemState.FALL_CONFIRMED,
                "ESP32 Advanced Hardware State Machine Confirmed Fall"
            )
            self.hardware_confirmed_fall = False
            current_state = SystemState.FALL_CONFIRMED
                
        # ── Rule 2: POSSIBLE_FALL → FALL_CONFIRMED (context-aware §8) ──
        if current_state == SystemState.POSSIBLE_FALL:
            inactivity_duration = current_time - self.last_movement_time
            
            if self.is_person_visible:
                # Person visible: use CV + wearable fusion
                time_diff = abs(self.last_cv_fall_time - self.last_accel_spike_time)
                
                # Presentation & Live Demo Rule: Confirm if camera detects fall with >= 80% confidence
                if self.last_cv_confidence >= 0.80 and (current_time - self.last_cv_fall_time) < 3.0:
                    self.state_manager.transition_to(
                        SystemState.FALL_CONFIRMED,
                        f"Camera-only fall confirmed (Confidence={self.last_cv_confidence:.0%})"
                    )
                elif fall_score >= self.FALL_SCORE_THRESHOLD:
                    self.state_manager.transition_to(
                        SystemState.FALL_CONFIRMED, 
                        f"Weighted score={fall_score:.2f} exceeded threshold"
                    )
                elif time_diff <= self.TIME_SYNC_WINDOW and self.last_cv_fall_time > 0 and self.last_accel_spike_time > 0:
                    self.state_manager.transition_to(
                        SystemState.FALL_CONFIRMED, 
                        "CV + Accel spike within sync window"
                    )
                elif self.last_cv_fall_time > 0 and inactivity_duration > self.INACTIVITY_TIMEOUT:
                    self.state_manager.transition_to(
                        SystemState.FALL_CONFIRMED, 
                        "CV fall + prolonged inactivity"
                    )
            else:
                # Person NOT visible: rely on wearable only (spec §8)
                if self.last_accel_spike_time > 0 and inactivity_duration > self.INACTIVITY_TIMEOUT:
                    self.state_manager.transition_to(
                        SystemState.FALL_CONFIRMED, 
                        "Wearable spike + inactivity (outside camera)"
                    )
                    
            # Recovery from false alarm: movement resumes (extended hold time to 15s)
            if inactivity_duration < 2.0 and (current_time - max(self.last_cv_fall_time, self.last_accel_spike_time)) > 15.0:
                self.state_manager.transition_to(SystemState.NORMAL, "Normal movement resumed, false alarm")

        # ── Rule 3: FALL_CONFIRMED → MEDICAL_ALERT (spec §10) ──
        current_state = self.state_manager.state
        if current_state == SystemState.FALL_CONFIRMED:
            audio_recent = (current_time - self.last_audio_distress_time) < 5.0
            
            # Only evaluate vitals for medical alert if we have a real sensor connection
            is_medical = False
            if self.vitals_connected:
                is_medical = (
                    spo2 < self.CRITICAL_SPO2 or
                    hr > self.CRITICAL_HR_HIGH or
                    hr < self.CRITICAL_HR_LOW or
                    audio_recent
                )
            elif audio_recent:
                is_medical = True  # Audio distress alone can trigger medical alert
            
            if is_medical:
                reasons = []
                if spo2 < self.CRITICAL_SPO2: reasons.append(f"SpO2={spo2}%")
                if hr > self.CRITICAL_HR_HIGH: reasons.append(f"HR={hr}BPM(high)")
                if hr < self.CRITICAL_HR_LOW: reasons.append(f"HR={hr}BPM(low)")
                if audio_recent: reasons.append("Audio distress")
                
                self.state_manager.transition_to(
                    SystemState.MEDICAL_ALERT, 
                    " + ".join(reasons)
                )
                self._log_event("MEDICAL_ALERT", fall_score, {"hr": hr, "spo2": spo2, "audio": audio_recent})
            else:
                # Fall confirmed but vitals OK → still send alert
                self.state_manager.transition_to(
                    SystemState.ALERT_SENT, 
                    "Fall confirmed, vitals stable"
                )
                self._log_event("FALL_ALERT_SENT", fall_score, {"hr": hr, "spo2": spo2})
                
        # ── Rule 4: MEDICAL_ALERT → ALERT_SENT ──
        if self.state_manager.state == SystemState.MEDICAL_ALERT:
            self.state_manager.transition_to(
                SystemState.ALERT_SENT, 
                "Emergency alert dispatched"
            )
            self._log_event("EMERGENCY_ALERT_SENT", fall_score, {"hr": hr, "spo2": spo2})
            
        return self.state_manager.get_current_state()
    
    # ──────────────────────────────────────────────
    # Event History
    # ──────────────────────────────────────────────
    def _log_event(self, event_type: str, confidence: float, metadata: dict):
        """Store an event for the dashboard Event History table."""
        event_record = {
            "timestamp": time.time(),
            "event_type": event_type,
            "confidence": round(confidence, 3),
            "metadata": metadata,
            "system_state": self.state_manager.get_current_state(),
        }
        self.event_history.append(event_record)
        
        # Keep last 100 events
        if len(self.event_history) > 100:
            self.event_history = self.event_history[-100:]
            
        # Log to SQLite
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO event_log (id, time, patient_id, event_type, confidence, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), event_record["timestamp"], self.patient_id, event_type, confidence, json.dumps(metadata)))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB Error: {e}")
    
    def get_snapshot(self) -> Dict[str, Any]:
        """Return complete current state for dashboard consumption."""
        return {
            "patient_id": self.patient_id,
            "system_state": self.state_manager.get_current_state(),
            "is_person_visible": self.is_person_visible,
            "fall_score": self.latest_fall_score,
            "vitals": self.latest_vitals,
            "motion": self.latest_motion,
            "audio": self.latest_audio,
            "state_history": self.state_manager.get_recent_history(10),
            "event_history": self.event_history[-20:],
        }
