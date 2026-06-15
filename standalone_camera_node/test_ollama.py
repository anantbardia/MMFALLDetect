import cv2
import time
import urllib.request
import numpy as np
from fall_detection import FallDetector

def run_test():
    print("Initializing FallDetector...")
    detector = FallDetector()
    
    print("Downloading test image of a person...")
    # URL of a random person standing
    url = "https://images.unsplash.com/photo-1515041219749-89347f83291a?w=400&q=80"
    req = urllib.request.urlopen(url)
    arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
    img = cv2.imdecode(arr, -1)
    
    print("Passing image to process_frame...")
    detector.process_frame(img)
    
    print("Waiting 20 seconds for Ollama background thread to respond...")
    for i in range(20):
        state = detector.current_posture_state
        print(f"[{i}s] Current State: {state}")
        if state not in ["ANALYZING...", "OLLAMA ERROR", "OLLAMA OFFLINE"]:
            print("Successfully got a valid response from Ollama!")
            break
        time.sleep(1)
        
    print(f"Final Detected Posture: {detector.current_posture_state}")
    detector.running = False

if __name__ == "__main__":
    run_test()
