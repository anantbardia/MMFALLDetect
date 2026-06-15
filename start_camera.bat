@echo off
title ShieldCare Camera Broadcaster & Presentation Starter
echo ============================================
echo   SHIELDCARE - Camera Broadcaster ^& Presentation Starter
echo ============================================
echo.

:: Kill any previous instances of ngrok
echo [CLEANUP] Stopping old tunnels...
taskkill /IM ngrok.exe /F >nul 2>&1

:: Check if stream server port is free, kill if occupied
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING" 2^>nul') do (
    echo [CLEANUP] Killing process on port 8001 (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)

:: Check if backend server port is free, kill if occupied
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING" 2^>nul') do (
    echo [CLEANUP] Killing process on port 8000 (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)

ping 127.0.0.1 -n 3 >nul

:: Start the backend server
echo [1/3] Starting Backend API Server on port 8000...
start "Backend Server" cmd /k "cd /d %~dp0 && python backend/api_server.py"

:: Start the camera stream server
echo [2/3] Starting Camera Stream Server on port 8001...
start "Camera Stream" cmd /k "cd /d %~dp0 && python cv_module/stream_server.py"

:: Wait for both servers to initialize fully (MediaPipe/TensorFlow load time)
echo       Waiting for ML models and camera to initialize...
ping 127.0.0.1 -n 15 >nul

:: Start ngrok tunnel on port 8000
echo [3/3] Starting Ngrok tunnel to broadcast backend ^& camera feed...
echo.
echo ============================================
echo   PRESENTATION MODE ACTIVE!
echo   1. Access Vercel Dashboard at:
echo      https://mmfall-detect.vercel.app/
echo   2. Click the gear settings icon (top-left of camera feed)
echo   3. Set Backend API URL to: 
echo      https://crouch-trapped-stock.ngrok-free.dev
echo   4. Set Camera Feed URL to:
echo      https://crouch-trapped-stock.ngrok-free.dev/video_feed
echo ============================================
echo.

ngrok http --url=crouch-trapped-stock.ngrok-free.dev 8000
