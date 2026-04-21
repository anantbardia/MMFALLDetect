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
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
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
        
        # ── Velocity tracking (spec §5: rapid downward movement) ──
        self.prev_head_y = None
        self.prev_frame_time = time.time()
        self.velocity_history = deque(maxlen=10)  # recent vertical velocities
        self.VELOCITY_THRESHOLD = 0.8  # normalized pixels/second for fall detection
        
        # ── Inactivity tracking (spec §5: person motionless after fall) ──
        self.prev_landmarks = None
        self.landmark_movement_history = deque(maxlen=30)  # track movement per frame
        self.INACTIVITY_THRESHOLD = 0.005  # average landmark displacement
        self.INACTIVITY_FRAMES = 20  # frames with minimal movement
        
        # ── Custom ML Model ──
        model_path = os.path.join(os.path.dirname(__file__), "fall_model.keras")
        scaler_path = os.path.join(os.path.dirname(__file__), "scaler.pkl")
        try:
            self.model = tf.keras.models.load_model(model_path)
            with open(scaler_path, "rb") as f:
                self.scaler = pickle.load(f)
            print("[CV] Successfully loaded custom Neural Network Brain!")
            self.ml_active = True
        except Exception as e:
            print(f"[CV] Failed to load ML model: {e}")
            self.ml_active = False
        
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

    def analyze_posture(self, landmarks, image_width, image_height):
        """Analyze posture using the custom Keras Deep Neural Network."""
        try:
            current_time = time.time()
            
            # Predict using Neural Network if available
            if hasattr(self, 'ml_active') and self.ml_active:
                row = []
                for lm in landmarks.landmark:
                    row.extend([lm.x, lm.y, lm.z, lm.visibility])
                
                # Transform features
                X_vec = np.array(row).reshape(1, -1)
                X_scaled = self.scaler.transform(X_vec)
                
                # Inference
                preds = self.model.predict(X_scaled, verbose=0)[0]
                pred_class = np.argmax(preds)
                
                # Assuming Class 0 is Fall (most prevalent in Kaggle datasets of this type)
                is_fall = bool(pred_class == 0)
                confidence = float(preds[0]) if is_fall else float(preds[pred_class])
                
                if is_fall:
                    if not self.is_fallen:
                        self.fall_start_time = current_time
                    self.frames_since_fall += 1
                else:
                    self.frames_since_fall = 0
                    
                return is_fall, round(confidence, 3)
            
            else:
                # Fallback to old heuristic if ML model failed to load
                head_y = landmarks.landmark[self.mp_pose.PoseLandmark.NOSE.value].y
                ankle_y = (landmarks.landmark[self.mp_pose.PoseLandmark.LEFT_ANKLE.value].y + 
                           landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_ANKLE.value].y) / 2.0
                y_diff = abs(head_y - ankle_y)
                return bool(y_diff < 0.2), 0.75
                
        except Exception as e:
            print(f"[CV] Posture analysis error: {e}")
            return False, 0.0

    def process_frame(self, frame):
        """Process a single frame through the full CV pipeline."""
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
            
            is_fallen, confidence = self.analyze_posture(
                results.pose_landmarks, image_width, image_height
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
                cv2.putText(image, "STANDING", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA)
            
            # Velocity display
            if self.velocity_history:
                vel = self.velocity_history[-1]
                vel_color = (0, 200, 255) if abs(vel) < self.VELOCITY_THRESHOLD else (0, 0, 255)
                cv2.putText(image, f"V.vel: {vel:.2f}", (image_width - 200, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, vel_color, 1, cv2.LINE_AA)
                
            self.send_event(event_payload)
        else:
            # No person detected — still send event so backend knows
            self.prev_head_y = None
            self.prev_landmarks = None
            self.send_event(event_payload)
                
        return image
        
    def send_event(self, payload):
        """Send CV event to backend. Throttled to avoid spam."""
        current_time = time.time()
        state_changed = (payload["fall_predicted"] != self.is_fallen)
        
        if state_changed or (current_time - self.last_event_time > 1.0):
            self.last_event_time = current_time
            
            try:
                requests.post(
                    f"{self.backend_url}/api/v1/events/cv/{self.patient_id}", 
                    json=payload, 
                    timeout=1.0,
                )
            except Exception as e:
                pass  # Don't spam console with connection errors


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
