@echo off
title ShieldCare Camera Broadcaster
echo ============================================
echo   SHIELDCARE - Camera Broadcaster
echo ============================================
echo.

:: Kill any previous instances
echo [CLEANUP] Stopping old processes...
taskkill /IM ngrok.exe /F >nul 2>&1

:: Check if stream server port is free, kill if occupied
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8001.*LISTENING" 2^>nul') do (
    echo [CLEANUP] Killing process on port 8001 (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)

ping 127.0.0.1 -n 3 >nul

:: Start the camera stream server in a minimized window
echo [1/2] Starting Camera Stream Server on port 8001...
start "Camera Stream" /min cmd /k "cd /d %~dp0 && python cv_module/stream_server.py"

:: Wait for the stream server to boot up
echo       Waiting for camera to initialize...
ping 127.0.0.1 -n 9 >nul

:: Start ngrok tunnel
echo [2/2] Starting Ngrok tunnel to broadcast camera...
echo.
echo ============================================
echo   IMPORTANT: Copy the HTTPS URL shown below
echo   and paste it into Vercel env variable:
echo   VITE_CAMERA_URL = [URL]/video_feed
echo ============================================
echo.

ngrok http 8001
