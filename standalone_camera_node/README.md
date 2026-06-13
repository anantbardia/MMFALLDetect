# Standalone Camera Node

This folder contains the **Standalone Computer Vision Node** for the MMFALLDetect project.
It has been perfectly decoupled from the rest of the workspace so you can easily copy this *exact folder* to a Raspberry Pi, an old laptop, or any secondary device acting as a dedicated camera monitor.

## Contents
1. `fall_detection.py` - The core mathematical and geometric state engine.
2. `stream_server.py` - The FastAPI MJPEG video stream broadcaster.
3. `requirements.txt` - Minimal required Python packages.
4. `run_camera.bat` - 1-click startup script for Windows.

## Deployment Instructions

### 1. Transfer
Copy this entire `standalone_camera_node` folder to your secondary device.

### 2. Run
Simply double-click `run_camera.bat` (on Windows). 
If you are on Linux/Raspberry Pi, run:
```bash
pip install -r requirements.txt
python stream_server.py
```

### 3. Expose to Internet (Ngrok)
If the secondary device is not on the same local network as your Cloud Backend, you will need to expose port `8001` via ngrok:
```bash
ngrok http 8001
```
Take the generated URL and save it into your Mobile App's Settings Screen under "Camera URL"!
