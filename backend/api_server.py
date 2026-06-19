import sys
import os
import time

# Add parent directory to path to allow importing core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio
from typing import Dict, Any, List

from core.decision_engine import DecisionEngine
from core.state_manager import SystemState
from pydantic import BaseModel
import requests
import threading

app = FastAPI(
    title="Multi-Modal Fall Detection API",
    description="Backend for the Intelligent Multi-Modal Fall Detection and Health Monitoring System",
    version="2.0.0",
)

# Setup CORS for Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# In-memory session tracking
# ──────────────────────────────────────────────
engines: Dict[str, DecisionEngine] = {}
active_connections: Dict[str, List[WebSocket]] = {}
import json
patient_push_tokens: Dict[str, str] = {}
TOKENS_FILE = os.path.join(os.path.dirname(__file__), "push_tokens.json")

try:
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "r") as f:
            patient_push_tokens = json.load(f)
except Exception as e:
    print(f"Failed to load push tokens: {e}")

def save_push_tokens():
    try:
        with open(TOKENS_FILE, "w") as f:
            json.dump(patient_push_tokens, f)
    except Exception as e:
        print(f"Failed to save push tokens: {e}")
# Simulated device registry (in production, this comes from DB)
device_registry: Dict[str, Dict[str, Any]] = {
    "AA:BB:CC:DD:EE:01": {
        "mac_address": "AA:BB:CC:DD:EE:01",
        "patient_id": "patient_01",
        "device_type": "WEARABLE",
        "battery_level": 87,
        "is_active": True,
        "last_seen": time.time(),
    },
    "CAM-01-LR": {
        "mac_address": "CAM-01-LR",
        "patient_id": "patient_01",
        "device_type": "CAMERA",
        "battery_level": 100,
        "is_active": True,
        "last_seen": time.time(),
    },
}

def get_engine(patient_id: str) -> DecisionEngine:
    if patient_id not in engines:
        engines[patient_id] = DecisionEngine(patient_id)
        active_connections[patient_id] = []
    return engines[patient_id]


def send_expo_push_notification(patient_id: str, title: str, body: str, data: dict = None):
    token = patient_push_tokens.get(patient_id)
    if not token:
        return
    
    def _send():
        try:
            response = requests.post(
                "https://exp.host/--/api/v2/push/send",
                json={
                    "to": token,
                    "title": title,
                    "body": body,
                    "data": data or {},
                    "sound": "default",
                    "priority": "high",
                    "_displayInForeground": True
                },
                headers={
                    "Accept": "application/json",
                    "Accept-encoding": "gzip, deflate",
                    "Content-Type": "application/json",
                },
                timeout=5.0
            )
            print(f"Expo Push Response: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Failed to send Expo push notification: {e}")

    threading.Thread(target=_send, daemon=True).start()


# ──────────────────────────────────────────────
# REST: General
# ──────────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "online", "message": "Multi-Modal Fall Detection API is running"}


# ──────────────────────────────────────────────
# WebSocket: Live Dashboard Feed
# ──────────────────────────────────────────────
@app.websocket("/ws/live-feed/{patient_id}")
async def live_feed_websocket(websocket: WebSocket, patient_id: str):
    await websocket.accept()
    engine = get_engine(patient_id)
    active_connections[patient_id].append(websocket)
    try:
        while True:
            # Send full snapshot every second as heartbeat
            snapshot = engine.get_snapshot()
            await websocket.send_json({"type": "heartbeat", **snapshot})
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        active_connections[patient_id].remove(websocket)
    except Exception:
        if websocket in active_connections.get(patient_id, []):
            active_connections[patient_id].remove(websocket)


# ──────────────────────────────────────────────
# REST: Ingest Events
# ──────────────────────────────────────────────
@app.post("/api/v1/events/cv/{patient_id}")
async def receive_cv_event(patient_id: str, event: Dict[str, Any]):
    """Receive a Computer Vision event from the CV edge module."""
    engine = get_engine(patient_id)
    old_state = engine.state_manager.get_current_state()
    
    # Update camera device last_seen
    for d in device_registry.values():
        if d["device_type"] == "CAMERA" and d["patient_id"] == patient_id:
            d["last_seen"] = time.time()
            d["is_active"] = True
    
    new_state = engine.process_cv_event(event)
    
    if new_state == "FALL_CONFIRMED" and old_state != "FALL_CONFIRMED":
        send_expo_push_notification(
            patient_id, 
            "CRITICAL ALERT: Fall Detected", 
            "A fall has been confirmed via computer vision. Please check the dashboard immediately.",
            {"event": "fall_confirmed", "source": "cv"}
        )

    await broadcast_event(patient_id, {
        "type": "cv_update", 
        "data": event, 
        "system_state": new_state,
        "fall_score": engine.latest_fall_score,
    })
    return {"status": "ok", "state": new_state, "fall_score": engine.latest_fall_score}


@app.post("/api/v1/events/iot/{patient_id}")
async def receive_iot_event(patient_id: str, event: Dict[str, Any]):
    """Receive a Wearable IoT event (motion + vitals + audio)."""
    engine = get_engine(patient_id)
    old_state = engine.state_manager.get_current_state()
    
    # Update wearable device last_seen and battery
    for d in device_registry.values():
        if d["device_type"] == "WEARABLE" and d["patient_id"] == patient_id:
            d["last_seen"] = time.time()
            d["is_active"] = True
            if "battery_level" in event:
                d["battery_level"] = event["battery_level"]
    
    # Uses engine's internal is_person_visible (context-aware, spec §8)
    new_state = engine.process_iot_event(event)

    if new_state == "FALL_CONFIRMED" and old_state != "FALL_CONFIRMED":
        send_expo_push_notification(
            patient_id, 
            "CRITICAL ALERT: Fall Detected", 
            "A fall has been confirmed via the wearable device. Please check the dashboard immediately.",
            {"event": "fall_confirmed", "source": "iot"}
        )

    await broadcast_event(patient_id, {
        "type": "iot_update", 
        "data": event, 
        "system_state": new_state,
        "fall_score": engine.latest_fall_score,
        "smv": engine.latest_motion["smv"],
    })
    return {"status": "ok", "state": new_state, "fall_score": engine.latest_fall_score}


# ──────────────────────────────────────────────
# REST: Status & History Queries
# ──────────────────────────────────────────────
@app.get("/api/v1/status/{patient_id}")
async def get_patient_status(patient_id: str):
    """Return current system state, vitals, visibility, and fall score."""
    engine = get_engine(patient_id)
    return engine.get_snapshot()


@app.get("/api/v1/history/{patient_id}")
async def get_event_history(patient_id: str):
    """Return recent event history for the Event History table."""
    engine = get_engine(patient_id)
    return {"events": engine.event_history[-50:]}


@app.get("/api/v1/devices")
async def get_devices():
    """Return health, battery level, and last ping time of all connected devices."""
    now = time.time()
    devices = []
    for d in device_registry.values():
        devices.append({
            **d,
            "seconds_since_seen": round(now - d["last_seen"], 1),
            "status": "ONLINE" if (now - d["last_seen"]) < 30 else "OFFLINE",
        })
    return {"devices": devices}


class PushTokenPayload(BaseModel):
    patient_id: str
    token: str

@app.post("/api/v1/notifications/register")
async def register_push_token(payload: PushTokenPayload):
    patient_push_tokens[payload.patient_id] = payload.token
    save_push_tokens()
    print(f"Registered push token for {payload.patient_id}: {payload.token}")
    return {"status": "ok"}


# ──────────────────────────────────────────────
# REST: Alert Management
# ──────────────────────────────────────────────
@app.post("/api/v1/alerts/{patient_id}/acknowledge")
async def acknowledge_alert(patient_id: str):
    """Reset system state through RECOVERY → NORMAL (spec §11)."""
    engine = get_engine(patient_id)
    engine.state_manager.reset_to_normal("Manually acknowledged via Dashboard")
    engine.reset_history()  # Wipe short-term AI memory to prevent immediate re-trigger
    new_state = engine.state_manager.get_current_state()
    await broadcast_event(patient_id, {"type": "system_state", "system_state": new_state})
    return {"status": "reset", "state": new_state}


# ──────────────────────────────────────────────
# WebSocket Broadcast Helper
# ──────────────────────────────────────────────
async def broadcast_event(patient_id: str, message: dict):
    if patient_id in active_connections:
        dead_connections = []
        for connection in active_connections[patient_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dc in dead_connections:
            active_connections[patient_id].remove(dc)


import requests
from fastapi.responses import StreamingResponse

@app.get("/video_feed")
def video_feed_proxy():
    """Proxy requests to the local camera stream server on port 8001."""
    def stream_generator():
        try:
            r = requests.get("http://localhost:8001/video_feed", stream=True, timeout=None)
            for chunk in r.iter_content(chunk_size=4096):
                yield chunk
        except Exception as e:
            print(f"Proxy error: {e}")
    return StreamingResponse(stream_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("api_server:app", host="0.0.0.0", port=port, reload=False)
