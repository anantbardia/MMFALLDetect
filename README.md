# MMFallDetect — Multi-Modal Fall Detection System

A real-time fall detection system combining **computer vision**, **IoT wearable sensors**, and a **VLM-based verification engine** for accurate elderly care monitoring.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   CV Module     │ ──▶ │                  │ ──▶ │   Web Dashboard  │
│ (MediaPipe+CV)  │     │   Backend API    │     │  (React + Vite)  │
├─────────────────┤     │  (FastAPI/Python)│     ├──────────────────┤
│   VLM Verifier  │ ──▶ │                  │ ──▶ │   Mobile App     │
│ (Ollama/LLaVA)  │     │  Fusion Engine   │     │  (React Native)  │
├─────────────────┤     │  + Notification  │     └──────────────────┘
│   IoT Wearable  │ ──▶ │                  │
│ (ESP32 + IMU)   │     │  MQTT Broker     │
└─────────────────┘     │  (Mosquitto)     │
                        └──────────────────┘
```

## Components

### 📷 Computer Vision Module (`cv_module/`)
- Real-time pose estimation via **MediaPipe Pose Landmarker**
- Skeletal feature extraction (torso angle, velocity, inactivity)
- Trained Keras classifier for fall detection
- VLM (LLaVA via Ollama) for semantic verification — distinguishes "on floor" vs "on furniture"

### ⌚ IoT Wearable Module (`iot_module/`)
- **ESP32-C3** firmware with 3-phase fall state machine
- **MPU6050** IMU for 6-DOF motion tracking
- **MAX30102** for heart rate / SpO₂ monitoring
- **SIM800L** GSM fallback for cellular alerts
- MQTT communication to backend

### ⚙️ Fusion Engine (`core/` + `backend/`)
- Weighted scoring model combining CV + IoT data
- Configurable decision thresholds via `decision_engine.py`
- State manager for alert escalation
- Event persistence (SQLite/PostgreSQL)
- Expo push notifications and SMS fallback via Twilio

### 🌐 Web Dashboard (`dashboard/`)
- Real-time camera feed with fall overlays
- Live vitals monitoring (HR, SpO₂, IMU telemetry)
- Event timeline with severity indicators
- Patient management and settings

### 📱 Mobile App (`mobile_app/`)
- Remote monitoring with push notifications
- Camera feed viewer
- Alert acknowledgment and settings
- Built with Expo + React Native

### 🎥 Standalone Camera Node (`standalone_camera_node/`)
- Self-contained deployment for remote cameras
- Independent fall detection pipeline
- Direct MQTT publishing

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 20+
- Ollama (for VLM verification)
- Mosquitto MQTT broker (Docker or native)

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
python api_server.py
```

### 2. CV Module
```bash
cd cv_module
pip install -r ../standalone_camera_node/requirements.txt
python stream_server.py
```

### 3. Web Dashboard
```bash
cd dashboard
npm install
npm run dev
```

### 4. Mobile App
```bash
cd mobile_app
npm install
npx expo start
```

### 5. Infrastructure (MQTT + Database)
```bash
docker-compose up -d
```

## Configuration

| File | Purpose |
|------|---------|
| `core/decision_engine.py` | Fusion scoring weights & thresholds |
| `core/state_manager.py` | Alert escalation state machine |
| `mosquitto/config/mosquitto.conf` | MQTT broker settings |
| `docker-compose.yml` | TimescaleDB + Mosquitto services |

## Model Files

Pre-trained models are included:
- `cv_module/pose_landmarker_lite.task` — MediaPipe pose landmarker
- `cv_module/fall_model.keras` — Keras fall classifier
- `cv_module/scaler.pkl` — Feature normalization scaler

## License

MIT — see [LICENSE](mobile_app/LICENSE).
