@echo off
echo ==============================================
echo   Starting Standalone MMFALLDetect CV Node
echo ==============================================
echo.

echo [1/2] Checking Python dependencies...
pip install -r requirements.txt -q

echo.
echo [2/2] Launching Fast MJPEG Camera Server...
python stream_server.py
pause
