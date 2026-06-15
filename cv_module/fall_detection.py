"""
Computer Vision Fall Detection Module (spec §5).

Pipeline:
  Camera Frame → Person Detection → Pose Estimation → 
  Body Orientation Analysis → Fall Detection → Generate Event

Detection methods:
  1. Bounding box aspect ratio (height/width < 1.0 → lying down)
  2. Vertical velocity tracking (rapid downward head movement)
  3. Inactivity detection (person motionless after falling)
  4. Dynamic confidence scoring from multiple signals
"""

import cv2
import mediapipe as mp
import numpy as np
import time
import math
import requests
import json
from collections import deque
import tensorflow as tf
import pickle
import os

class FallDetector:
    def __init__(self, backend_url="http://localhost:8000", patient_id="patient_01"):
        # ── MediaPipe Setup ──
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=0.3,
            min_tracking_confidence=0.3,
            model_complexity=0,
        )
        self.mp_drawing = mp.solutions.drawing_utils
        
        # ── Network ──
        self.backend_url = backend_url
        self.patient_id = patient_id
        
        # ── State tracking ──
        self.is_fallen = False
        self.fall_start_time = 0
        self.last_event_time = 0
        self.frames_since_fall = 0
        self.inference_counter = 0
        self.last_prediction = (False, 0.0)
        
        # ── Velocity tracking (spec §5: rapid downward movement) ──
        self.prev_head_y = None
        self.prev_frame_time = time.time()
        self.velocity_history = deque(maxlen=20)  # ~0.66s at 30fps
        self.VELOCITY_THRESHOLD = 0.8  # normalized pixels/second for fall detection
        
        # ── Inactivity tracking (spec §5: person motionless after fall) ──
        self.prev_landmarks = None
        self.landmark_movement_history = deque(maxlen=30)  # track movement per frame
        self.INACTIVITY_THRESHOLD = 0.005  # average landmark displacement
        self.INACTIVITY_FRAMES = 20  # frames with minimal movement
        
        # ── Custom ML Model (DISABLED in favor of Geometric Logic) ──
        self.ml_active = False
        self.current_posture_state = "UNKNOWN"
        self.fall_confirmed_latch = False
        self.fall_latch_time = 0
        
        # ── Smoothing Filters ──
        self.smoothed_torso_angle = None
        self.smoothed_knee_angle = None
        self.ALPHA = 0.5  # Balanced: reacts quickly but filters single-frame noise
        
    def calculate_bbox_ratio(self, landmarks, image_width, image_height):
        """Calculate height-to-width ratio of the body bounding box.
        > 1.0 = standing (taller than wide)
        < 1.0 = lying down (wider than tall)
        """
        x_coords = [lm.x for lm in landmarks.landmark]
        y_coords = [lm.y for lm in landmarks.landmark]
        
        width = (max(x_coords) - min(x_coords)) * image_width
        height = (max(y_coords) - min(y_coords)) * image_height
        
        if width == 0:
            width = 0.001
        
        return height / width

    def compute_vertical_velocity(self, head_y: float, current_time: float) -> float:
        """Track vertical velocity of the head (spec §5: rapid downward movement)."""
        if self.prev_head_y is None:
            self.prev_head_y = head_y
            self.prev_frame_time = current_time
            return 0.0
            
        dt = current_time - self.prev_frame_time
        if dt <= 0:
            return 0.0
            
        # Positive velocity = downward movement (Y increases downward in image coords)
        velocity = (head_y - self.prev_head_y) / dt
        
        self.prev_head_y = head_y
        self.prev_frame_time = current_time
        self.velocity_history.append(velocity)
        
        return velocity
    
    def compute_landmark_movement(self, landmarks) -> float:
        """Compute average displacement of all landmarks between frames.
        Used for inactivity detection (spec §5: person motionless after fall).
        """
        current_pts = [(lm.x, lm.y) for lm in landmarks.landmark]
        
        if self.prev_landmarks is None:
            self.prev_landmarks = current_pts
            return 1.0  # assume movement on first frame
            
        total_disp = 0.0
        for (cx, cy), (px, py) in zip(current_pts, self.prev_landmarks):
            total_disp += math.sqrt((cx - px)**2 + (cy - py)**2)
        
        avg_disp = total_disp / len(current_pts)
        self.prev_landmarks = current_pts
        self.landmark_movement_history.append(avg_disp)
        
        return avg_disp
    
    def is_person_inactive(self) -> bool:
        """Check if person has been motionless for N frames."""
        if len(self.landmark_movement_history) < self.INACTIVITY_FRAMES:
            return False
        recent = list(self.landmark_movement_history)[-self.INACTIVITY_FRAMES:]
        avg_movement = sum(recent) / len(recent)
        return avg_movement < self.INACTIVITY_THRESHOLD

    def get_line_angle(self, p1_x, p1_y, p2_x, p2_y):
        """Calculate angle of a line relative to the X-axis in 2D."""
        dx = abs(p1_x - p2_x)
        dy = abs(p1_y - p2_y)
        if dx == 0:
            return 90.0
        return math.degrees(math.atan2(dy, dx))

    def get_3d_angle(self, p1, p2, p3):
        """Calculate the 3D angle between three points (p1-p2-p3)."""
        # p2 is the vertex (e.g., knee)
        ba = [p1.x - p2.x, p1.y - p2.y, p1.z - p2.z]
        bc = [p3.x - p2.x, p3.y - p2.y, p3.z - p2.z]
        
        dot_product = sum(a * b for a, b in zip(ba, bc))
        mag_ba = math.sqrt(sum(a**2 for a in ba))
        mag_bc = math.sqrt(sum(b**2 for b in bc))
        
        if mag_ba * mag_bc == 0:
            return 180.0
            
        cos_angle = dot_product / (mag_ba * mag_bc)
        cos_angle = max(-1.0, min(1.0, cos_angle)) # Handle precision errors
        
        return math.degrees(math.acos(cos_angle))

    def analyze_posture(self, landmarks, image_width, image_height, current_velocity):
        """Analyze posture using deterministic geometric state machine and velocity."""
        try:
            current_time = time.time()
            lm = landmarks.landmark
            mp_pose = self.mp_pose.PoseLandmark
            
            # Extract Midpoints
            shoulder_x = (lm[mp_pose.LEFT_SHOULDER.value].x + lm[mp_pose.RIGHT_SHOULDER.value].x) / 2
            shoulder_y = (lm[mp_pose.LEFT_SHOULDER.value].y + lm[mp_pose.RIGHT_SHOULDER.value].y) / 2
            
            hip_x = (lm[mp_pose.LEFT_HIP.value].x + lm[mp_pose.RIGHT_HIP.value].x) / 2
            hip_y = (lm[mp_pose.LEFT_HIP.value].y + lm[mp_pose.RIGHT_HIP.value].y) / 2
            
            # Calculate Angles
            torso_angle = self.get_line_angle(shoulder_x, shoulder_y, hip_x, hip_y)
            
            # --- OVERHAUL 2.0: Femur-Height & Face-Proximity Gates ---
            left_hip, left_knee, left_ankle = lm[mp_pose.LEFT_HIP.value], lm[mp_pose.LEFT_KNEE.value], lm[mp_pose.LEFT_ANKLE.value]
            right_hip, right_knee, right_ankle = lm[mp_pose.RIGHT_HIP.value], lm[mp_pose.RIGHT_KNEE.value], lm[mp_pose.RIGHT_ANKLE.value]
            
            torso_height = max(abs(hip_y - shoulder_y), 0.001)
            
            # 1. Sitting Math: When sitting, the femur (hip to knee) becomes horizontal (2D vertical height shrinks to near 0)
            avg_knee_y = (left_knee.y + right_knee.y) / 2.0
            femur_height = abs(avg_knee_y - hip_y)
            femur_torso_ratio = femur_height / torso_height
            
            # 2. Close-up Math: If the face takes up > 15% of the screen width, it's a camera-in-face false positive.
            face_width = abs(lm[mp_pose.LEFT_EAR.value].x - lm[mp_pose.RIGHT_EAR.value].x)
            is_close_up = face_width > 0.15
            
            # ── 1. Temporal Smoothing (EMA) ──
            if not hasattr(self, 'smoothed_femur_ratio') or self.smoothed_torso_angle is None:
                self.smoothed_torso_angle = torso_angle
                self.smoothed_femur_ratio = femur_torso_ratio
            else:
                self.smoothed_torso_angle = (self.ALPHA * torso_angle) + ((1 - self.ALPHA) * self.smoothed_torso_angle)
                self.smoothed_femur_ratio = (self.ALPHA * femur_torso_ratio) + ((1 - self.ALPHA) * self.smoothed_femur_ratio)
            
            # ── 2. Strict Occlusion & Visibility Gates ──
            # MediaPipe guesses off-screen landmarks, so we must check if they are actually off-screen (y > 1.0 or y < 0.0)
            legs_off_screen = (avg_knee_y > 0.95) or (left_ankle.y > 0.95 and right_ankle.y > 0.95)
            
            # ── 3. Multi-Factor Fall Proximity & Normalization ──
            head_y = lm[mp_pose.NOSE.value].y
            avg_ankle_y = (left_ankle.y + right_ankle.y) / 2.0
            head_ankle_dist = abs(head_y - avg_ankle_y)
            
            # Bounding box height
            bbox_min_y = min(node.y for node in lm)
            bbox_max_y = max(node.y for node in lm)
            bbox_height = max(bbox_max_y - bbox_min_y, 0.001)
            
            # Normalized velocity (raw velocity divided by body height)
            max_recent_vel = max(list(self.velocity_history) + [0])
            normalized_vel = max_recent_vel / bbox_height
            
            # Strict flat check: Head must be near ankles relative to total bounding box
            is_physically_flat = (head_ankle_dist / bbox_height) < 0.5
            
            # Fall triggers (falling 10% of own body height in a single frame = ~30 FPS rapid drop)
            has_rapid_drop = normalized_vel > 0.10
            
            is_fall = False
            confidence = 0.0
            
            # Maintain fall latch for 5 seconds to avoid flickering
            if self.fall_confirmed_latch and (current_time - self.fall_latch_time < 5.0):
                # Check for recovery: strong upward velocity means person is standing up
                min_recent_vel = min(list(self.velocity_history) + [0])
                if (min_recent_vel / bbox_height) < -0.08:  # Upward movement
                    self.fall_confirmed_latch = False
                    self.velocity_history.clear()
                else:
                    self.current_posture_state = "FALL DETECTED"
                    return True, 0.99
            elif self.fall_confirmed_latch:
                self.fall_confirmed_latch = False
                self.velocity_history.clear()  # Decay old velocities on latch expiry
            
            # State Machine Logic
            if self.smoothed_torso_angle > 50.0:
                # Torso is generally upright
                if is_close_up or legs_off_screen:
                    self.current_posture_state = "STANDING"
                elif self.smoothed_femur_ratio < 0.65:
                    # Femur vertical height is small relative to torso -> SITTING
                    self.current_posture_state = "SITTING"
                else:
                    # Femur vertical height is long -> STANDING
                    self.current_posture_state = "STANDING"
            elif self.smoothed_torso_angle > 30.0 and head_y < hip_y:
                # BENDING GATE: 30-50° torso with head still above hips
                self.current_posture_state = "BENDING"
            else:
                # Torso is horizontal (angle < 30, or < 50 with head at/below hips)
                if is_close_up:
                    self.current_posture_state = "STANDING"
                elif has_rapid_drop and is_physically_flat:
                    # Rapid normalized drop AND head is close to the floor -> TRUE FALL!
                    self.current_posture_state = "FALL DETECTED"
                    self.fall_confirmed_latch = True
                    self.fall_latch_time = current_time
                    is_fall = True
                    confidence = 0.98
                else:
                    # Slow transition OR lying on furniture -> RESTING
                    self.current_posture_state = "SLEEPING"
            
            if is_fall:
                if not self.is_fallen:
                    self.fall_start_time = current_time
                self.frames_since_fall += 1
            else:
                self.frames_since_fall = 0
                
            return is_fall, confidence
                
        except Exception as e:
            print(f"[CV] Posture analysis error: {e}")
            self.current_posture_state = "ERROR"
            return False, 0.0

    def process_frame(self, frame):
        """Process a single frame through the full CV pipeline."""
        previous_is_fallen = self.is_fallen
        image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image.flags.writeable = False
        
        results = self.pose.process(image)
        
        image.flags.writeable = True
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        image_height, image_width, _ = image.shape
        event_payload = {
            "person_visible": False,
            "fall_predicted": False,
            "confidence": 0.0,
            "timestamp": time.time(),
        }

        if results.pose_landmarks:
            event_payload["person_visible"] = True
            
            # Draw skeleton
            self.mp_drawing.draw_landmarks(
                image, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS,
                self.mp_drawing.DrawingSpec(color=(245,117,66), thickness=2, circle_radius=2),
                self.mp_drawing.DrawingSpec(color=(245,66,230), thickness=2, circle_radius=2),
            )
            
            # Calculate velocity BEFORE analyzing posture
            head_y = results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.NOSE.value].y
            current_vel = self.compute_vertical_velocity(head_y, time.time())
            
            # Track overall body movement for inactivity detection
            self.compute_landmark_movement(results.pose_landmarks)
            
            is_fallen, confidence = self.analyze_posture(
                results.pose_landmarks, image_width, image_height, current_vel
            )
            
            if is_fallen:
                event_payload["fall_predicted"] = True
                event_payload["confidence"] = confidence
                self.is_fallen = True
                
                # Red overlay
                color = (0, 0, 255)
                label = f"FALL DETECTED (conf={confidence:.0%})"
                cv2.putText(image, label, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
                
                # Inactivity timer
                if self.is_person_inactive():
                    elapsed = time.time() - self.fall_start_time
                    cv2.putText(image, f"MOTIONLESS: {elapsed:.0f}s", (30, 90), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2, cv2.LINE_AA)
            else:
                self.is_fallen = False
                
                # Dynamic Color based on state
                state_color = (0, 255, 0)
                if self.current_posture_state == "SITTING":
                    state_color = (255, 200, 0) # Cyan/Blueish for Sitting
                elif self.current_posture_state == "SLEEPING":
                    state_color = (255, 100, 200) # Purpleish for Sleeping
                    
                cv2.putText(image, self.current_posture_state, (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, state_color, 2, cv2.LINE_AA)
            
            # Velocity display
            if self.velocity_history:
                vel = self.velocity_history[-1]
                vel_color = (0, 200, 255) if abs(vel) < self.VELOCITY_THRESHOLD else (0, 0, 255)
                cv2.putText(image, f"V.vel: {vel:.2f}", (image_width - 200, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, vel_color, 1, cv2.LINE_AA)
                
            self.send_event(event_payload, previous_is_fallen)
        else:
            # No person detected — still send event so backend knows
            self.prev_head_y = None
            self.prev_landmarks = None
            self.is_fallen = False
            self.send_event(event_payload, previous_is_fallen)
                
        return image
        
    def send_event(self, payload, previous_is_fallen):
        """Send CV event to backend. Throttled to avoid spam."""
        current_time = time.time()
        state_changed = (payload["fall_predicted"] != previous_is_fallen)
        
        if state_changed or (current_time - self.last_event_time > 1.0):
            self.last_event_time = current_time
            
            import threading
            def _post():
                try:
                    requests.post(
                        f"{self.backend_url}/api/v1/events/cv/{self.patient_id}", 
                        json=payload, 
                        timeout=5.0,
                    )
                except Exception as e:
                    print(f"[Network] Backend event failed: {e}")
            threading.Thread(target=_post, daemon=True).start()


if __name__ == "__main__":
    detector = FallDetector()
    cap = cv2.VideoCapture(0)
    
    print("=" * 50)
    print("  Multi-Modal Fall Detection — CV Module")
    print("  Press ESC to exit")
    print("=" * 50)
    
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            continue
        
        output_frame = detector.process_frame(frame)
        cv2.imshow("Multi-Modal Fall Detection CV", output_frame)
        
        if cv2.waitKey(5) & 0xFF == 27:
            break
            
    cap.release()
    cv2.destroyAllWindows()
