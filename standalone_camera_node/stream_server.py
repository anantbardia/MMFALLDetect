import sys
import os
import cv2
import uvicorn
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

# Ensure local imports work correctly for standalone package
from fall_detection import FallDetector

app = FastAPI(title="CV Stream Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
detector = FallDetector(
    backend_url=backend_url,
    patient_id="patient_01"
)

import threading
import time

class ThreadedCamera:
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.grabbed, self.frame = self.cap.read()
        self.frame_id = 0
        self.stopped = False
        threading.Thread(target=self.update, daemon=True).start()
        
    def update(self):
        while not self.stopped:
            grabbed, frame = self.cap.read()
            if grabbed:
                self.grabbed = grabbed
                self.frame = frame
                self.frame_id += 1
            
    def read(self):
        return self.grabbed, self.frame, self.frame_id

cap = ThreadedCamera(0)

def generate_frames():
    last_frame_id = -1
    while True:
        success, frame, frame_id = cap.read()
        if not success or frame is None:
            time.sleep(0.01)
            continue
            
        # Prevent churning the CPU by processing the exact same frame multiple times
        if frame_id == last_frame_id:
            time.sleep(0.01)
            continue
            
        # Ensure fast processing resolution
        frame = cv2.resize(frame, (640, 480))
        output_frame = detector.process_frame(frame)
        last_frame_id = frame_id
        
        # Fast JPEG Compression
        ret, buffer = cv2.imencode('.jpg', output_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        if not ret:
            continue
            
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

if __name__ == "__main__":
    print("[INFO] Starting M-JPEG stream server on http://localhost:8001/video_feed")
    uvicorn.run(app, host="0.0.0.0", port=8001)
