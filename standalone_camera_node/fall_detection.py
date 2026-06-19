"""
Computer Vision Fall Detection Module — Ironclad Hybrid Architecture.

Pipeline:
  Camera Frame -> MediaPipe Geometry (Torso Angle, Femur Height, Velocity, Inactivity)
  -> Multi-Gate State Machine (Bending, Close-Up, Legs-Off-Screen, Recovery)
  -> If Horizontal & Low -> LLaVA VLM Confirmation
  -> Fall Latch (5s hold to prevent flicker)
  -> Event Generation to Backend
"""

import cv2
import time
import math
import requests
import base64
import threading
from collections import deque
import mediapipe as mp


class FallDetector:
    def __init__(self, backend_url="http://localhost:8000", patient_id="patient_01"):
        self.backend_url = backend_url
        self.patient_id = patient_id

        # ── Core State ──
        self.is_fallen = False
        self.last_event_time = 0
        self.current_posture_state = "INITIALIZING..."
        self.confidence = 0.0

        # ── Fall Latch (prevents flicker: holds fall state for 5s) ──
        self.fall_latch_active = False
        self.fall_latch_time = 0
        self.FALL_LATCH_DURATION = 5.0

        # ── Velocity Tracking ──
        self.prev_head_y = None
        self.prev_frame_time = time.time()
        self.velocity_history = deque(maxlen=20)  # ~0.66s at 30fps

        # ── Smoothing Filters (EMA) ──
        self.smoothed_torso_angle = None
        self.smoothed_femur_ratio = None
        self.ALPHA = 0.5  # Balanced: reacts quickly but filters noise

        # ── Inactivity Tracking (post-fall motionlessness) ──
        self.prev_landmarks = None
        self.landmark_movement_history = deque(maxlen=30)
        self.INACTIVITY_THRESHOLD = 0.005
        self.INACTIVITY_FRAMES = 15
        self.fall_start_time = 0

        # ── CV Fall Debounce (require N consecutive fall frames) ──
        self.consecutive_fall_frames = 0
        self.FALL_FRAME_THRESHOLD = 3  # Need 3 consecutive horizontal+low frames

        # ── VLM Temporal Voting ──
        self.prediction_history = deque(maxlen=3)

        # ── MediaPipe Setup (Tasks API) ──
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        base_options = python.BaseOptions(model_asset_path='pose_landmarker_lite.task')
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False,
            min_pose_detection_confidence=0.3,
            min_pose_presence_confidence=0.3,
            min_tracking_confidence=0.3)
        self.detector = vision.PoseLandmarker.create_from_options(options)

        # Landmark indices (MediaPipe Tasks API uses list indices)
        self.NOSE = 0
        self.LEFT_EAR, self.RIGHT_EAR = 7, 8
        self.LEFT_SHOULDER, self.RIGHT_SHOULDER = 11, 12
        self.LEFT_HIP, self.RIGHT_HIP = 23, 24
        self.LEFT_KNEE, self.RIGHT_KNEE = 25, 26
        self.LEFT_ANKLE, self.RIGHT_ANKLE = 27, 28

        # ── Ollama VLM Setup ──
        self.latest_frame_for_vlm = None
        self.vlm_state = "AWAITING VLM..."
        self.ollama_url = "http://localhost:11434/api/generate"
        self.vlm_active = False
        self.geometric_hint = "UNKNOWN"

        self.running = True
        self.inference_thread = threading.Thread(target=self._ollama_inference_loop, daemon=True)
        self.inference_thread.start()

    # ─── Geometric Helpers ────────────────────────────
    def get_line_angle(self, p1_x, p1_y, p2_x, p2_y):
        """Angle of line relative to X-axis. 90° = vertical, 0° = horizontal."""
        dx = abs(p1_x - p2_x)
        dy = abs(p1_y - p2_y)
        if dx == 0:
            return 90.0
        return math.degrees(math.atan2(dy, dx))

    def compute_vertical_velocity(self, head_y: float, current_time: float) -> float:
        """Track head's vertical velocity. Positive = downward."""
        if self.prev_head_y is None:
            self.prev_head_y = head_y
            self.prev_frame_time = current_time
            return 0.0
        dt = current_time - self.prev_frame_time
        if dt <= 0:
            return 0.0
        velocity = (head_y - self.prev_head_y) / dt
        self.prev_head_y = head_y
        self.prev_frame_time = current_time
        self.velocity_history.append(velocity)
        return velocity

    # ─── Inactivity Detection ─────────────────────────
    def compute_landmark_movement(self, landmarks) -> float:
        """Average displacement of all landmarks between consecutive frames."""
        current_pts = [(pt.x, pt.y) for pt in landmarks]
        if self.prev_landmarks is None:
            self.prev_landmarks = current_pts
            return 1.0  # Assume movement on first frame
        total_disp = 0.0
        for (cx, cy), (px, py) in zip(current_pts, self.prev_landmarks):
            total_disp += math.sqrt((cx - px) ** 2 + (cy - py) ** 2)
        avg_disp = total_disp / len(current_pts)
        self.prev_landmarks = current_pts
        self.landmark_movement_history.append(avg_disp)
        return avg_disp

    def is_person_inactive(self) -> bool:
        """Check if person has been motionless for N frames."""
        if len(self.landmark_movement_history) < self.INACTIVITY_FRAMES:
            return False
        recent = list(self.landmark_movement_history)[-self.INACTIVITY_FRAMES:]
        return (sum(recent) / len(recent)) < self.INACTIVITY_THRESHOLD

    # ─── VLM Inference Thread ─────────────────────────
    def _ollama_inference_loop(self):
        """Background thread: runs continuously when a person is detected to provide context-aware posture classification."""
        while self.running:
            if not self.vlm_active or self.latest_frame_for_vlm is None:
                time.sleep(0.1)
                continue
            try:
                small_frame = cv2.resize(self.latest_frame_for_vlm, (224, 224))
                _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                b64_image = base64.b64encode(buffer).decode('utf-8')

                hint = getattr(self, 'geometric_hint', 'UNKNOWN')
                prompt = (
                    f"Geometry: '{hint}'. Classify posture: STANDING, SITTING, BENDING, LYING_FLOOR, LYING_BED. Answer with exactly 1 word."
                )

                payload = {
                    "model": "llava",
                    "prompt": prompt,
                    "images": [b64_image],
                    "stream": False,
                    "options": {
                        "num_predict": 5,
                        "temperature": 0.1
                    }
                }

                response = requests.post(self.ollama_url, json=payload, timeout=10.0)
                if response.status_code == 200:
                    result_text = response.json().get("response", "").strip().upper()

                    raw_prediction = "VLM: UNKNOWN"
                    if "STANDING" in result_text:
                        raw_prediction = "STANDING"
                    elif "SITTING" in result_text:
                        raw_prediction = "SITTING"
                    elif "BENDING" in result_text:
                        raw_prediction = "BENDING"
                    elif "LYING_FLOOR" in result_text or "FLOOR" in result_text:
                        raw_prediction = "FALL DETECTED"
                    elif "LYING_BED" in result_text or "BED" in result_text or "FURNITURE" in result_text:
                        raw_prediction = "SLEEPING"

                    self.prediction_history.append(raw_prediction)
                    fall_votes = sum(1 for p in self.prediction_history if p == "FALL DETECTED")

                    if fall_votes >= 2:
                        self.vlm_state = "FALL DETECTED"
                        self.confidence = 0.98
                    else:
                        self.vlm_state = raw_prediction
                    
                    # Prevent VLM from hogging 100% CPU and killing camera stream FPS
                    time.sleep(0.5)
                else:
                    self.vlm_state = "OLLAMA ERROR"
                    time.sleep(2.0)
            except requests.exceptions.ConnectionError:
                self.vlm_state = "OLLAMA OFFLINE"
                time.sleep(3.0)
            except Exception as e:
                print(f"[VLM Error] {e}")
                self.vlm_state = "OLLAMA ERROR"
                time.sleep(2.0)

    # ─── Main Frame Processor ─────────────────────────
    def process_frame(self, frame):
        previous_is_fallen = self.is_fallen
        output_image = frame.copy()
        current_time = time.time()

        # ── MediaPipe Detection ──
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        detection_result = self.detector.detect(mp_image)

        if not detection_result.pose_landmarks:
            self.is_fallen = False
            self.vlm_active = True
            self.geometric_hint = "NO_PERSON_DETECTED"
            self.latest_frame_for_vlm = frame.copy()
            self.consecutive_fall_frames = 0
            self.prev_head_y = None
            self.prev_landmarks = None
            
            # Allow VLM to override "NO PERSON" if it spots someone lying down
            if self.vlm_state in ["FALL DETECTED", "SLEEPING", "STANDING", "SITTING", "BENDING"]:
                self.current_posture_state = f"{self.vlm_state} (VLM OVERRIDE)"
                if self.vlm_state == "FALL DETECTED":
                    self.is_fallen = True
            else:
                self.current_posture_state = "NO PERSON DETECTED"
                self.prediction_history.clear()
                
            self._finalize_frame(output_image, previous_is_fallen)
            return output_image

        lm = detection_result.pose_landmarks[0]

        # Draw skeleton dots
        image_height, image_width, _ = output_image.shape
        for pt in lm:
            x, y = int(pt.x * image_width), int(pt.y * image_height)
            cv2.circle(output_image, (x, y), 4, (245, 117, 66), -1)

        # Track inactivity
        self.compute_landmark_movement(lm)

        # ── 1. Geometric Feature Extraction ──
        shoulder_x = (lm[self.LEFT_SHOULDER].x + lm[self.RIGHT_SHOULDER].x) / 2
        shoulder_y = (lm[self.LEFT_SHOULDER].y + lm[self.RIGHT_SHOULDER].y) / 2
        hip_x = (lm[self.LEFT_HIP].x + lm[self.RIGHT_HIP].x) / 2
        hip_y = (lm[self.LEFT_HIP].y + lm[self.RIGHT_HIP].y) / 2

        torso_angle = self.get_line_angle(shoulder_x, shoulder_y, hip_x, hip_y)

        left_knee, right_knee = lm[self.LEFT_KNEE], lm[self.RIGHT_KNEE]
        left_ankle, right_ankle = lm[self.LEFT_ANKLE], lm[self.RIGHT_ANKLE]

        torso_height = max(abs(hip_y - shoulder_y), 0.001)
        avg_knee_y = (left_knee.y + right_knee.y) / 2.0
        femur_height = abs(avg_knee_y - hip_y)
        femur_torso_ratio = femur_height / torso_height

        face_width = abs(lm[self.LEFT_EAR].x - lm[self.RIGHT_EAR].x)
        is_close_up = face_width > 0.15

        # EMA Smoothing
        if self.smoothed_torso_angle is None:
            self.smoothed_torso_angle = torso_angle
            self.smoothed_femur_ratio = femur_torso_ratio
        else:
            self.smoothed_torso_angle = (self.ALPHA * torso_angle) + ((1 - self.ALPHA) * self.smoothed_torso_angle)
            self.smoothed_femur_ratio = (self.ALPHA * femur_torso_ratio) + ((1 - self.ALPHA) * self.smoothed_femur_ratio)

        # Velocity
        head_y = lm[self.NOSE].y
        current_vel = self.compute_vertical_velocity(head_y, current_time)

        # Bounding box metrics
        bbox_min_y = min(node.y for node in lm)
        bbox_max_y = max(node.y for node in lm)
        bbox_height = max(bbox_max_y - bbox_min_y, 0.001)

        max_recent_vel = max(list(self.velocity_history) + [0])
        normalized_vel = max_recent_vel / bbox_height

        avg_ankle_y = (left_ankle.y + right_ankle.y) / 2.0
        head_ankle_dist = abs(head_y - avg_ankle_y)
        is_physically_flat = (head_ankle_dist / bbox_height) < 0.5
        has_rapid_drop = normalized_vel > 0.10

        legs_off_screen = (avg_knee_y > 0.95) or (left_ankle.y > 0.95 and right_ankle.y > 0.95)

        # Head-above-hips check (for bending gate)
        head_above_hips = head_y < hip_y

        # Recovery detection: strong upward velocity = standing back up
        min_recent_vel = min(list(self.velocity_history) + [0])
        is_recovering = (min_recent_vel / bbox_height) < -0.08  # Upward movement

        # ── 2. Fall Latch Logic ──
        if self.fall_latch_active:
            elapsed = current_time - self.fall_latch_time
            if elapsed < self.FALL_LATCH_DURATION and not is_recovering:
                # Hold the fall state
                self.current_posture_state = f"FALL DETECTED ({self.FALL_LATCH_DURATION - elapsed:.0f}s)"
                self.is_fallen = True
                if self.is_person_inactive():
                    inactivity_secs = current_time - self.fall_start_time
                    cv2.putText(output_image, f"MOTIONLESS: {inactivity_secs:.0f}s", (20, 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2, cv2.LINE_AA)
                self._finalize_frame(output_image, previous_is_fallen)
                return output_image
            else:
                # Latch expired or person recovering
                self.fall_latch_active = False
                self.velocity_history.clear()  # Decay old velocities on recovery

        # ── 3. Multi-Gate State Machine ──
        is_fall_candidate = False

        if self.smoothed_torso_angle > 50.0:
            # ── UPRIGHT TORSO ──
            self.geometric_hint = "UPRIGHT"
            self.vlm_active = True
            self.latest_frame_for_vlm = frame.copy()
            self.is_fallen = False
            self.consecutive_fall_frames = 0
            
            if self.vlm_state in ["STANDING", "SITTING", "BENDING", "SLEEPING"]:
                self.current_posture_state = f"{self.vlm_state} (VLM)"
            else:
                if is_close_up or legs_off_screen:
                    self.current_posture_state = "STANDING"
                elif self.smoothed_femur_ratio < 0.65:
                    self.current_posture_state = "SITTING"
                else:
                    self.current_posture_state = "STANDING"

        elif self.smoothed_torso_angle > 30.0 and head_above_hips:
            # ── BENDING GATE (30-50° torso, head still above hips) ──
            self.geometric_hint = "BENDING"
            self.vlm_active = True
            self.latest_frame_for_vlm = frame.copy()
            
            if self.vlm_state in ["STANDING", "SITTING", "BENDING", "SLEEPING"]:
                self.current_posture_state = f"{self.vlm_state} (VLM)"
            else:
                self.current_posture_state = "BENDING"
                
            self.is_fallen = False
            self.consecutive_fall_frames = 0

        else:
            # ── HORIZONTAL TORSO (< 30° or < 50° with head at/below hips) ──
            self.geometric_hint = "HORIZONTAL"
            if is_close_up:
                self.current_posture_state = "STANDING (CLOSE-UP)"
                self.vlm_active = False
                self.is_fallen = False
                self.consecutive_fall_frames = 0
            else:
                # They are horizontal — activate VLM
                self.vlm_active = True
                self.latest_frame_for_vlm = frame.copy()
                is_fall_candidate = True

        # ── 4. Fall Decision (only if candidate) ──
        if is_fall_candidate:
            self.consecutive_fall_frames += 1

            if has_rapid_drop and is_physically_flat and self.consecutive_fall_frames >= self.FALL_FRAME_THRESHOLD:
                # RAPID FALL: Instant velocity + flat body + sustained horizontal
                self.current_posture_state = f"RAPID FALL -> {self.vlm_state}"
                if self.vlm_state != "SLEEPING":
                    self.is_fallen = True
                    self.confidence = 0.99
                    self.fall_latch_active = True
                    self.fall_latch_time = current_time
                    self.fall_start_time = current_time
                else:
                    self.is_fallen = False
            elif self.consecutive_fall_frames >= self.FALL_FRAME_THRESHOLD:
                # SLOW FALL / LYING: Wait for VLM to confirm floor vs furniture
                self.current_posture_state = f"ANALYZING -> {self.vlm_state}"
                if self.vlm_state == "FALL DETECTED":
                    self.is_fallen = True
                    self.confidence = 0.90
                    self.fall_latch_active = True
                    self.fall_latch_time = current_time
                    self.fall_start_time = current_time
                else:
                    self.is_fallen = False
            else:
                # Still accumulating consecutive frames
                self.current_posture_state = f"CHECKING... ({self.consecutive_fall_frames}/{self.FALL_FRAME_THRESHOLD})"
                self.is_fallen = False

        self._finalize_frame(output_image, previous_is_fallen)
        return output_image

    # ─── Frame Finalization & Event Dispatch ──────────
    def _finalize_frame(self, output_image, previous_is_fallen):
        event_payload = {
            "person_visible": "NO PERSON" not in self.current_posture_state,
            "fall_predicted": self.is_fallen,
            "confidence": self.confidence if self.is_fallen else 0.0,
            "timestamp": time.time(),
        }
        self.send_event(event_payload, previous_is_fallen)

        # Draw state on frame
        color = (0, 255, 0)  # Green
        if self.is_fallen:
            color = (0, 0, 255)  # Red
        elif "BENDING" in self.current_posture_state:
            color = (0, 200, 200)  # Yellow
        elif "ANALYZING" in self.current_posture_state or "RAPID" in self.current_posture_state:
            color = (0, 165, 255)  # Orange
        elif "CHECKING" in self.current_posture_state:
            color = (200, 200, 0)  # Cyan

        cv2.putText(output_image, f"STATE: {self.current_posture_state}", (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)

        # Show inactivity timer if fallen
        if self.is_fallen and self.is_person_inactive():
            elapsed = time.time() - self.fall_start_time
            cv2.putText(output_image, f"MOTIONLESS: {elapsed:.0f}s", (20, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2, cv2.LINE_AA)

    def send_event(self, payload, previous_is_fallen):
        """Send CV event to backend. Throttled to prevent spam."""
        current_time = time.time()
        state_changed = (payload["fall_predicted"] != previous_is_fallen)
        if state_changed or (current_time - self.last_event_time > 1.0):
            self.last_event_time = current_time

            def _post():
                try:
                    requests.post(
                        f"{self.backend_url}/api/v1/events/cv/{self.patient_id}",
                        json=payload, timeout=5.0
                    )
                except Exception as e:
                    print(f"[Network] Backend event failed: {e}")

            threading.Thread(target=_post, daemon=True).start()

    def __del__(self):
        self.running = False
