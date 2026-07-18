# MMFallDetect — Multi-Modal Fall Detection System

A real-time fall detection system fusing **computer vision** (MediaPipe + LLaVA VLM), **IoT wearable sensors** (ESP32-C3 + IMU), and a **multi-modal fusion engine** for accurate elderly care monitoring with push notification alerts.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SENSING LAYER                                │
│  ┌─────────────────────┐          ┌──────────────────────────────┐  │
│  │  CV Module           │          │  IoT Wearable Module         │  │
│  │  (Python/MediaPipe)  │          │  (ESP32-C3 + ISM330DHCX)    │  │
│  │                     │          │                              │  │
│  │  • Pose Landmarker  │          │  • 3-Phase Fall State Mach.  │  │
│  │  • EMA Smoothing    │          │  • 3D Spatial Tilt Engine    │  │
│  │  • VLM (LLaVA)      │───MQTT───│  • Free-Fall Detection       │  │
│  │  • Fall Latch (5s)  │          │  • Impact/Inactivity Gates   │  │
│  └─────────────────────┘          │  • MAX30102 Vitals           │  │
│                                   │  • SIM800L GSM Fallback      │  │
│                                   └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FUSION ENGINE (FastAPI)                        │
│                                                                     │
│  Weighted Score = 0.4×CV + 0.3×Motion + 0.2×Inactivity + 0.1×Audio │
│                                                                     │
│  State Machine: NORMAL → POSSIBLE_FALL → FALL_CONFIRMED             │
│                → MEDICAL_ALERT → ALERT_SENT → RECOVERY → NORMAL     │
│                                                                     │
│  • Expo Push Notification Dispatch                                  │
│  • WebSocket Live Feed Broadcasting                                 │
│  • SQLite/PostgreSQL Event Persistence                              │
│  • MQTT Listener (HiveMQ Cloud / Local Mosquitto)                  │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
        ┌─────────────────────┐   ┌──────────────────────────┐
        │  Web Dashboard      │   │  Mobile App              │
        │  (React + Vite)     │   │  (React Native + Expo)   │
        │                     │   │                          │
        │  • Live Camera      │   │  • Push Notifications    │
        │  • Vitals Graphs    │   │  • Camera Feed           │
        │  • Event Timeline   │   │  • Alert Acknowledgment  │
        │  • MQTT Live Data   │   │  • Patient Settings      │
        └─────────────────────┘   └──────────────────────────┘
```

## Key Features

- **Multi-Gate CV Pipeline** — MediaPipe 33-point skeletal landmark tracking with EMA smoothing, velocity analysis, and 5-second fall latch to prevent flicker
- **VLM Semantic Verification** — LLaVA (via Ollama) distinguishes "on floor" vs "on furniture", with temporal voting across 3 frames to eliminate LLM hallucination
- **Wearable 3-Phase State Machine** — ESP32 firmware requires sequential: free-fall (<0.7g) → impact (>3.2g) → 3D spatial tilt verification (>45° orientation change) → post-impact inactivity
- **Weighted Fusion Engine** — Configurable scoring: 40% CV confidence + 30% motion spike + 20% inactivity duration + 10% audio distress, with graceful degradation if any sensor is offline
- **GSM Fallback** — SIM800L module triggers SMS/call alert when Wi-Fi is unavailable
- **Expo Push Notifications** — Real-time alerts dispatched to mobile app on fall confirmation
- **Context-Aware Visibility** — Fusion engine adapts thresholds when person is outside camera frame (wearable-only mode)

## Components

### Computer Vision Module (`cv_module/`)
- **fall_detection.py** — Core detector class using MediaPipe Pose Landmarker (Lite model)
  - Extracts torso angle, femur-to-torso ratio, head vertical velocity, landmark displacement
  - EMA smoothing with alpha=0.5 for jitter reduction
  - Multi-gate state machine: upright, bending, horizontal, close-up, legs-off-screen
  - VLM background thread queries LLaVA via Ollama when horizontal posture detected
  - 3-frame consecutive fall threshold + 5-second fall latch
- **stream_server.py** — FastAPI M-JPEG stream server on port 8001, proxies frames through detector
- **pose_landmarker_lite.task** — MediaPipe pose estimation model
- **fall_model.keras** / **scaler.pkl** — Trained Keras classifier and feature normalizer

### IoT Wearable Module (`iot_module/`)
- **esp32_firmware_master.ino** — Full firmware with 3-phase state machine:
  - Phase 1: Free-fall prerequisite (SMV < 0.7g)
  - Phase 2: Impact trigger (SMV > 3.2g)
  - Phase 3: 3D spatial tilt verification (dot-product angle > 45°)
  - Post-impact inactivity check
  - MAX30102 optical heuristic (Red/IR differential) for skin contact verification
  - SIM800L GSM SMS/call fallback
- **esp32_firmware_no_gsm.ino** — Variant without GSM module
- **mqtt_listener.py** — Python MQTT subscriber forwarding wearable data to backend REST API

### Fusion Engine (`core/` + `backend/`)
- **decision_engine.py** — Weighted multi-modal scoring with configurable thresholds
- **state_manager.py** — Finite state machine enforcing valid transitions
- **api_server.py** — FastAPI server (port 8000):
  - `POST /api/v1/events/cv/{patient_id}` — Ingest CV events
  - `POST /api/v1/events/iot/{patient_id}` — Ingest wearable events
  - `GET /api/v1/status/{patient_id}` — Current system state snapshot
  - `GET /api/v1/history/{patient_id}` — Recent event history
  - `GET /api/v1/devices` — Device health and battery levels
  - `POST /api/v1/alerts/{patient_id}/acknowledge` — Manual alert reset
  - `POST /api/v1/notifications/register` — Register Expo push tokens
  - `WS /ws/live-feed/{patient_id}` — WebSocket broadcast to dashboards
  - `GET /video_feed` — M-JPEG proxy to CV stream
- **db_schema.sql** — SQLite schema (patients, devices, motion_data, vital_signs, audio_events, event_log)
- **falldetection.db** — Auto-created SQLite database

### Web Dashboard (`dashboard/`)
- React 19 + TypeScript + Vite 6
- Tailwind CSS + Recharts + Lucide icons
- Real-time MQTT subscription via Paho
- Live camera feed, vitals graphs, event timeline, device status panel

### Mobile App (`mobile_app/`)
- React Native + Expo 56
- Firebase authentication
- Paho MQTT for real-time data
- Expo Notifications for push alerts
- Screens: Dashboard, Events, Login, Settings

### Standalone Camera Node (`standalone_camera_node/`)
- Self-contained deployment with its own copy of the detection pipeline
- Independent MQTT publishing to backend
- Windows batch launchers (`run_camera.bat`, `run_broadcaster.bat`)

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 20+
- Ollama with LLaVA model (`ollama pull llava`)
- Mosquitto MQTT broker or Docker

### Setup

```bash
# 1. Start infrastructure (MQTT + TimescaleDB)
docker-compose up -d

# 2. Initialize database
cd backend
pip install -r requirements.txt
python db_setup.py
cd ..

# 3. Start backend API (port 8000)
cd backend
python api_server.py &
cd ..

# 4. Start CV module with camera (port 8001)
cd cv_module
pip install -r ../standalone_camera_node/requirements.txt
python stream_server.py &
cd ..

# 5. Start MQTT listener
pip install paho-mqtt requests  # if not installed
python iot_module/mqtt_listener.py &
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Backend API port |
| `MQTT_BROKER_HOST` | HiveMQ Cloud URL | MQTT broker address |
| `MQTT_BROKER_PORT` | `8883` | MQTT broker port |
| `MQTT_USERNAME` | — | MQTT username |
| `MQTT_PASSWORD` | — | MQTT password |
| `BACKEND_URL` | `http://localhost:8000` | Backend API URL for CV module |

### Web Dashboard

```bash
cd dashboard
npm install
npm run dev
```

### Mobile App

```bash
cd mobile_app
npm install
npx expo start
```

## State Machine

```
NORMAL ────→ POSSIBLE_FALL ────→ FALL_CONFIRMED ────→ MEDICAL_ALERT ────→ ALERT_SENT
  ↑                │                    │                                    │
  └────────────────┘                    └────────→ RECOVERY ←────────────────┘
```

- **NORMAL** → **POSSIBLE_FALL**: CV fall detected (3 consecutive frames, debounced) OR accelerometer spike > 2.0g
- **POSSIBLE_FALL** → **FALL_CONFIRMED**: Weighted score > 0.55, OR CV+accel within 3s sync window, OR CV confidence > 80%, OR wearable-only fall with inactivity
- **FALL_CONFIRMED** → **MEDICAL_ALERT**: Critical vitals (HR > 120 / < 45, SpO2 < 92%) or audio distress
- **FALL_CONFIRMED** → **ALERT_SENT**: Fall confirmed, vitals stable
- **ALERT_SENT** → **RECOVERY** → **NORMAL**: Manual acknowledgment via dashboard
- **NORMAL** / **ALERT_SENT**: Auto-recovery after 60s without new evidence

## Scoring Weights

| Component | Weight | Description |
|-----------|--------|-------------|
| CV confidence | 0.4 | Recent fall prediction confidence × temporal recency |
| Motion spike | 0.3 | Recent accelerometer SMV spike (> 2.0g) |
| Inactivity | 0.2 | Seconds since last movement (normalized to 10s) |
| Audio distress | 0.1 | Recent distress sound detection |

Threshold: Fall confirmed when weighted score > **0.55**.

## Deployment

### Cloud (Render)
```bash
# start.sh launches MQTT listener + backend API
./start.sh
```

### Standalone Camera Node (Windows)
```bash
cd standalone_camera_node
run_camera.bat   # Starts CV stream + backend + ngrok/localtunnel
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Computer Vision | Python, MediaPipe, OpenCV, LLaVA (Ollama) |
| Wearable Firmware | Arduino (ESP32-C3), ISM330DHCX IMU, MAX30102, SIM800L |
| Backend | FastAPI, Uvicorn, SQLite, TimescaleDB |
| MQTT Broker | HiveMQ Cloud / Eclipse Mosquitto |
| Web Dashboard | React 19, TypeScript, Vite, Tailwind CSS, Recharts, Paho MQTT |
| Mobile App | React Native, Expo 56, Firebase, Paho MQTT |
| Notifications | Expo Push Notifications, Twilio (SMS) |

## License

MIT — see [mobile_app/LICENSE](mobile_app/LICENSE).
