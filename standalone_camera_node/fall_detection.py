"""
Computer Vision Fall Detection Module (Hybrid Architecture).

Pipeline:
  Camera Frame -> Blur Check -> MediaPipe Geometry Gatekeeper -> 
  (If Horizontal) -> Moondream VLM Confirmation -> Event Generation
"""

import cv2
import time
import requests
import base64
import threading
from collections import deque
import mediapipe as mp

class FallDetector:
    def __init__(self, backend_url="http://localhost:8000", patient_id="patient_01"):
        self.backend_url = backend_url
        self.patient_id = patient_id
        
        # ── State tracking ──
        self.is_fallen = False
        self.last_event_time = 0
        self.current_posture_state = "INITIALIZING..."
        self.confidence = 0.0
        
        # ── Advanced Temporal Voting (for VLM) ──
        self.prediction_history = deque(maxlen=3)
        
        # ── MediaPipe Gatekeeper Setup ──
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        
        try:
            base_options = python.BaseOptions(model_asset_path='pose_landmarker_lite.task')
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                output_segmentation_masks=False,
                min_pose_detection_confidence=0.3,
                min_pose_presence_confidence=0.3,
                min_tracking_confidence=0.3)
            self.detector = vision.PoseLandmarker.create_from_options(options)
        except Exception as e:
            print(f"Error loading MediaPipe model: {e}")
            self.detector = None
            
        self.LEFT_EAR = 7
        self.RIGHT_EAR = 8
        
        # ── Ollama VLM Setup ──
        self.latest_frame_for_vlm = None
        self.vlm_state = "AWAITING VLM..."
        self.ollama_url = "http://localhost:11434/api/generate"
        
        # Start background polling thread for VLM
        self.running = True
        self.inference_thread = threading.Thread(target=self._ollama_inference_loop, daemon=True)
        self.inference_thread.start()
        
    def _ollama_inference_loop(self):
        """Background thread that ONLY runs when MediaPipe detects a horizontal body."""
        while self.running:
            if self.latest_frame_for_vlm is None:
                time.sleep(0.1)
                continue
                
            try:
                # 1. Grab the latest frame sent by the gatekeeper
                small_frame = cv2.resize(self.latest_frame_for_vlm, (400, 300))
                
                # 2. Encode to JPEG base64 (STRICTLY IN RAM - NO DISK SAVING)
                _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                b64_image = base64.b64encode(buffer).decode('utf-8')
                
                del small_frame
                del buffer
                # 3. Object-Based Prompt
                # Small AI models struggle with abstract actions like "falling" vs "sleeping".
                # But they are EXCELLENT at identifying physical objects (floor vs bed).
                prompt = "The person is lying down. Look at what is underneath them. Are they lying on the FLOOR, or are they lying on a BED or SOFA? Answer with exactly one word: FLOOR or FURNITURE."
                
                payload = {
                    "model": "llama3.2-vision",
                    "prompt": prompt,
                    "images": [b64_image],
                    "stream": False
                }
                
                response = requests.post(self.ollama_url, json=payload, timeout=10.0)
                if response.status_code == 200:
                    raw_json = response.json()
                    result_text = raw_json.get("response", "").strip().upper()
                    
                    if "NOT" in result_text:
                        result_text = result_text.replace("NOT FLOOR", "FURNITURE")
                        result_text = result_text.replace("NOT FURNITURE", "FLOOR")
                        
                    raw_prediction = "VLM: UNKNOWN"
                    if "FLOOR" in result_text or "GROUND" in result_text or "CARPET" in result_text:
                        raw_prediction = "FALL DETECTED"
                    elif "FURNITURE" in result_text or "BED" in result_text or "SOFA" in result_text or "CHAIR" in result_text:
                        raw_prediction = "SLEEPING"
                        
                    # ── Temporal Smoothing (Voting System) ──
                    self.prediction_history.append(raw_prediction)
                    fall_votes = sum(1 for p in self.prediction_history if p == "FALL DETECTED")
                    
                    if fall_votes >= 2:
                        self.vlm_state = "FALL DETECTED"
                        self.confidence = 0.98
                    else:
                        self.vlm_state = raw_prediction
                        
                else:
                    self.vlm_state = "OLLAMA ERROR"
                    time.sleep(2.0)
                    
            except requests.exceptions.ConnectionError:
                self.vlm_state = "OLLAMA OFFLINE"
                time.sleep(2.0)
            except Exception as e:
                print(f"[Ollama Thread Error] {e}")
                time.sleep(1.0)

    def process_frame(self, frame):
        """Main CV loop. Uses Geometry to gatekeep the VLM."""
        previous_is_fallen = self.is_fallen
        output_image = frame.copy()
        
        # 1. ── Blur Detection Gate ──
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        if blur_score < 30.0:
            self.current_posture_state = "MOTION BLUR (CAMERA MOVING)"
            self.is_fallen = False
            self.latest_frame_for_vlm = None
            self._finalize_frame(output_image, previous_is_fallen)
            return output_image
            
        # 2. ── MediaPipe Geometry Gatekeeper ──
        if not self.detector:
            self.current_posture_state = "MEDIAPIPE MODEL MISSING"
            self._finalize_frame(output_image, previous_is_fallen)
            return output_image
            
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        detection_result = self.detector.detect(mp_image)
        
        if not detection_result.pose_landmarks:
            self.current_posture_state = "NO PERSON DETECTED"
            self.is_fallen = False
            self.latest_frame_for_vlm = None
            self.prediction_history.clear()
            self._finalize_frame(output_image, previous_is_fallen)
            return output_image
            
        # We have a person! Extract 2D geometry
        landmarks = detection_result.pose_landmarks[0]
        
        # Draw skeleton
        image_height, image_width, _ = output_image.shape
        for pt in landmarks:
            x = int(pt.x * image_width)
            y = int(pt.y * image_height)
            cv2.circle(output_image, (x, y), 4, (245, 117, 66), -1)
            
        # Calculate bounding box
        x_coords = [lm.x for lm in landmarks]
        y_coords = [lm.y for lm in landmarks]
        
        bbox_width = max((max(x_coords) - min(x_coords)), 0.001)
        bbox_height = max((max(y_coords) - min(y_coords)), 0.001)
        
        # Calculate face width relative to screen
        face_width = abs(landmarks[self.LEFT_EAR].x - landmarks[self.RIGHT_EAR].x)
        
        # Check which body parts are visible
        # MediaPipe uses visibility scores. If hips/knees are not visible, we only see the upper body.
        # Since we use a simple list of landmarks without visibility in the old loop, we can just check 
        # if the Y coordinates of the bottom of the bounding box are close to the top of the bounding box.
        
        # ── IRONCLAD GEOMETRIC RULES ──
        if face_width > 0.25:
            # Rule 1: The face takes up >25% of the screen width. 
            # This is someone looking right into the camera. It is physically impossible to be a fall.
            self.current_posture_state = "STANDING (CLOSE-UP)"
            self.is_fallen = False
            self.latest_frame_for_vlm = None
            self.prediction_history.clear()
            
        elif bbox_height > bbox_width:
            # Rule 2: The bounding box is taller than it is wide. 
            # The person is absolutely upright (standing or sitting).
            self.current_posture_state = "UPRIGHT (STANDING/SITTING)"
            self.is_fallen = False
            self.latest_frame_for_vlm = None
            self.prediction_history.clear()
            
        else:
            # Rule 3: The bounding box is wider than it is tall.
            # This could mean they are lying down horizontally.
            
            # ── FLOOR GATE ──
            # Look at the absolute lowest point of their body (max_y). 
            # If they are floating in the top 60% of the screen, they are elevated on a bed/sofa.
            # The floor is at the bottom of the screen (Y closer to 1.0).
            max_y = max(y_coords)
            
            if max_y < 0.60:
                self.current_posture_state = "ELEVATED (SLEEPING/RESTING)"
                self.is_fallen = False
                self.latest_frame_for_vlm = None
                self.prediction_history.clear()
            else:
                # They are horizontal AND low to the ground.
                # Now we ask Moondream: Is this a mattress on the floor, or the actual floor?
                self.current_posture_state = f"ANALYZING... -> {self.vlm_state}"
                self.latest_frame_for_vlm = frame.copy()
                
                if self.vlm_state == "FALL DETECTED":
                    self.is_fallen = True
                else:
                    self.is_fallen = False
                
        self._finalize_frame(output_image, previous_is_fallen)
        return output_image
        
    def _finalize_frame(self, output_image, previous_is_fallen):
        # Send event
        event_payload = {
            "person_visible": "NO PERSON" not in self.current_posture_state and "BLUR" not in self.current_posture_state,
            "fall_predicted": self.is_fallen,
            "confidence": self.confidence if self.is_fallen else 0.0,
            "timestamp": time.time(),
        }
        self.send_event(event_payload, previous_is_fallen)
        
        # Draw UI
        color = (0, 255, 0)
        if self.is_fallen:
            color = (0, 0, 255)
        elif "HORIZONTAL" in self.current_posture_state:
            color = (0, 165, 255) # Orange warning
        elif "BLUR" in self.current_posture_state or "MISSING" in self.current_posture_state:
            color = (150, 150, 150)
            
        cv2.putText(output_image, f"STATE: {self.current_posture_state}", (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)

    def send_event(self, payload, previous_is_fallen):
        current_time = time.time()
        state_changed = (payload["fall_predicted"] != previous_is_fallen)
        
        if state_changed or (current_time - self.last_event_time > 1.0):
            self.last_event_time = current_time
            def _post():
                try:
                    requests.post(
                        f"{self.backend_url}/api/v1/events/cv/{self.patient_id}", 
                        json=payload, 
                        timeout=1.0,
                    )
                except Exception:
                    pass
            threading.Thread(target=_post, daemon=True).start()

    def __del__(self):
        self.running = False

if __name__ == "__main__":
    detector = FallDetector()
    cap = cv2.VideoCapture(0)
    print("=" * 50)
    print("  Hybrid Fall Detection (MediaPipe + Moondream)")
    print("  Press ESC to exit")
    print("=" * 50)
    while cap.isOpened():
        success, frame = cap.read()
        if not success: continue
        cv2.imshow("Hybrid CV", detector.process_frame(frame))
        if cv2.waitKey(5) & 0xFF == 27: break
    detector.running = False
    cap.release()
    cv2.destroyAllWindows()
