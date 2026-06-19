@echo off
title MMFALLDetect - Broadcasting Camera Node

echo ==============================================================
echo     Starting MMFALLDetect Broadcasting Camera Node
echo ==============================================================
echo.

echo Cleaning up old background processes...
taskkill /F /IM ngrok.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
echo.

:: Automatically setting the Render Backend URL (Hardcoded)
set BACKEND_URL=https://mmfalldetect.onrender.com
echo [✓] Backend Target: %BACKEND_URL%
echo.

echo [1/3] Creating Isolated Python Virtual Environment...
if not exist "venv" (
    python -m venv venv
    echo [✓] Created new clean environment.
)

echo [2/3] Installing Pristine Dependencies (This may take a moment on first run)...
call venv\Scripts\activate
pip install mediapipe==0.10.14 opencv-python fastapi uvicorn requests ollama -q

echo.
echo [3/5] Pulling LLaVA AI Model (this may take a moment on first run)...
ollama pull llava

echo.
echo [4/5] Downloading MediaPipe Pose Model (if missing)...
if not exist "pose_landmarker_lite.task" (
    powershell -Command "Invoke-WebRequest -Uri 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task' -OutFile 'pose_landmarker_lite.task'"
    echo [✓] Downloaded pose_landmarker_lite.task
)

echo.
echo [5/5] Launching Fast MJPEG Camera Server...
:: Use "start" to run it in a separate window so the script can continue
start "CV Stream Server" cmd /c "call venv\Scripts\activate && set CAMERA_SOURCE=2 && python stream_server.py & pause"

echo ==============================================================
echo Launching Ngrok Tunnel on port 8001...
echo [✓] Custom Domain: crouch-trapped-stock.ngrok-free.dev
echo.
:: Run ngrok in this window using the specific domain
ngrok http --domain=crouch-trapped-stock.ngrok-free.dev 127.0.0.1:8001

pause
