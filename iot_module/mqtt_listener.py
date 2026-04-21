"""
MQTT Listener for Wearable IoT Patch (spec §14 data flow).

Subscribes to MQTT topics published by the ESP32 wearable device
and forwards sensor messages to the Backend Decision Engine via REST API.

Topics:
  fall_detection/motion/{patient_id}  -> acceleration + gyro data
  fall_detection/vitals/{patient_id}  -> heart rate + SpO2
  fall_detection/audio/{patient_id}   -> distress audio detection
"""

import json
import time
import requests
import paho.mqtt.client as mqtt

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
BACKEND_URL = "http://localhost:8000"
DEFAULT_PATIENT_ID = "patient_01"

# MQTT topic patterns
TOPIC_MOTION = "fall_detection/motion/#"
TOPIC_VITALS = "fall_detection/vitals/#"
TOPIC_AUDIO  = "fall_detection/audio/#"


def extract_patient_id(topic: str) -> str:
    """Extract patient_id from topic like 'fall_detection/motion/patient_01'."""
    parts = topic.split("/")
    return parts[2] if len(parts) >= 3 else DEFAULT_PATIENT_ID


# ──────────────────────────────────────────────
# MQTT Callbacks
# ──────────────────────────────────────────────
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Connected to broker successfully")
        client.subscribe(TOPIC_MOTION)
        client.subscribe(TOPIC_VITALS)
        client.subscribe(TOPIC_AUDIO)
        print(f"[MQTT] Subscribed to: {TOPIC_MOTION}, {TOPIC_VITALS}, {TOPIC_AUDIO}")
    else:
        print(f"[MQTT] Connection failed with code {rc}")


def on_message(client, userdata, msg):
    """Process incoming MQTT message and forward to backend."""
    import traceback
    try:
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode())
        except json.JSONDecodeError:
            print(f"[MQTT] Invalid JSON on topic {topic}")
            return
        
        patient_id = extract_patient_id(topic)
        iot_event = {}
        
        if "motion" in topic:
            iot_event = {
                "ax": payload.get("ax", 0.0),
                "ay": payload.get("ay", 0.0),
                "az": payload.get("az", 0.0),
                "gyro": payload.get("gyro", 0.0),
                "motion": payload.get("motion", "normal"),
                "battery_level": payload.get("battery_level"),
                "timestamp": payload.get("timestamp", time.time()),
            }
        elif "vitals" in topic:
            iot_event = {
                "heart_rate": payload.get("heart_rate"),
                "spo2": payload.get("spo2"),
                "timestamp": payload.get("timestamp", time.time()),
            }
        elif "audio" in topic:
            iot_event = {
                "distress_sound_detected": payload.get("distress_detected", False),
                "audio_activity": payload.get("audio_activity", False),
                "timestamp": payload.get("timestamp", time.time()),
            }
        
        try:
            url = f"{BACKEND_URL}/api/v1/events/iot/{patient_id}"
            
            def send_req():
                try:
                    resp = requests.post(url, json=iot_event, timeout=2.0)
                    print(f"[MQTT -> API] {topic} | state={resp.json().get('state')} | score={resp.json().get('fall_score')}")
                except Exception as e:
                    print(f"[API ERROR] {e}")

            import threading
            threading.Thread(target=send_req, daemon=True).start()
            
        except Exception as e:
            print(f"[MQTT] Error forwarding event: {e}")
            
    except Exception as e:
        err = traceback.format_exc()
        print(f"[MQTT] FATAL on_message error: {err}")
        with open("listener_debug.txt", "w") as f:
            f.write(err)

def on_disconnect(client, userdata, rc):
    print(f"[MQTT] Disconnected (rc={rc}). Attempting reconnect...")
    with open("listener_disconnect.txt", "a") as f:
        f.write(f"Disconnected with rc={rc}\n")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    client = mqtt.Client(client_id="fall_detection_listener")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    print(f"[MQTT] Connecting to broker at {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}...")
    
    try:
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
        client.loop_forever()
    except ConnectionRefusedError:
        print(f"[MQTT] ERROR: Cannot connect to broker at {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
        print("[MQTT] Make sure Mosquitto is installed and running.")
    except KeyboardInterrupt:
        print("[MQTT] Shutting down listener...")
        client.disconnect()


if __name__ == "__main__":
    main()
