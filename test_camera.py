"""
Camera Fall Detection Test Script
==================================
This launches your webcam and runs the CV fall detection pipeline.
It will show the camera feed with skeleton overlay and fall detection status.

HOW TO TEST FALL DETECTION:
  1. Stand normally in front of the camera → should say "STANDING"
  2. Slowly bend down / crouch / lie on a couch → should say "FALL DETECTED"
  3. Stay still after "falling" → should show "MOTIONLESS: Xs" timer
  4. Stand back up → should return to "STANDING"

The CV module sends events to the backend at http://localhost:8000, 
which updates the dashboard in real time.

REQUIREMENTS:
  pip install opencv-python mediapipe requests

USAGE:
  python test_camera.py
  
Press ESC to exit.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cv_module.fall_detection import FallDetector
import cv2

def main():
    print("=" * 60)
    print("  MULTI-MODAL FALL DETECTION — Camera Test")
    print("=" * 60)
    print()
    print("  HOW TO TEST:")
    print("  1. Stand normally        → 'STANDING' (green)")
    print("  2. Crouch / lie down     → 'FALL DETECTED' (red)")
    print("  3. Stay still after fall → 'MOTIONLESS: Xs' (orange)")
    print("  4. Stand back up         → Returns to 'STANDING'")
    print()
    print("  The dashboard at http://localhost:5173 updates live.")
    print("  Press ESC in the camera window to exit.")
    print("=" * 60)
    print()
    
    detector = FallDetector(
        backend_url="http://localhost:8000",
        patient_id="patient_01",
    )
    
    # Try to open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open webcam (camera index 0).")
        print("  Make sure your webcam is connected and not in use by another app.")
        print("  If you have multiple cameras, edit 'cv2.VideoCapture(0)' to 1, 2, etc.")
        return
    
    print("[OK] Webcam opened successfully.")
    print("[OK] Backend connection: http://localhost:8000")
    print()
    
    while True:
        success, frame = cap.read()
        if not success:
            print("[WARN] Failed to read frame from webcam. Retrying...")
            continue
        
        # Process through fall detection pipeline
        output_frame = detector.process_frame(frame)
        
        # Add test instructions overlay
        cv2.putText(output_frame, "Test: Crouch/lie down to trigger fall detection",
                     (10, output_frame.shape[0] - 20),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(output_frame, "ESC to exit",
                     (output_frame.shape[1] - 120, output_frame.shape[0] - 20),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1, cv2.LINE_AA)
        
        cv2.imshow("Fall Detection Camera Test", output_frame)
        
        # ESC to exit
        if cv2.waitKey(5) & 0xFF == 27:
            break
    
    cap.release()
    cv2.destroyAllWindows()
    print("\n[DONE] Camera test ended.")


if __name__ == "__main__":
    main()
