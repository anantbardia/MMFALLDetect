import cv2
import sys

def test_cameras():
    print("Scanning for connected webcams...\n")
    working_cameras = []
    
    for i in range(5):
        # Test default backend
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                print(f"[SUCCESS] Camera index {i} is working (Default Backend)")
                working_cameras.append(i)
        cap.release()
        
    print("\nIf you have a built-in laptop webcam, it is usually index 0.")
    print("Your Google Pixel 'Android Webcam' is likely index 1 or 2.")
    print("\nTo start the stream server with index 1, run:")
    print("  $env:CAMERA_SOURCE=\"1\"")
    print("  python stream_server.py")

if __name__ == "__main__":
    test_cameras()
