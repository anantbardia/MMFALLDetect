#!/bin/bash
# Startup script for Render

# Run the MQTT listener in the background
echo "Starting MQTT Listener..."
python iot_module/mqtt_listener.py &

# Run the FastAPI server in the foreground
echo "Starting API Server..."
cd backend
uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}
