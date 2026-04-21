"""
IoT Sensor Simulator
=====================
Simulates wearable sensor data (motion + vitals + audio) being sent to the backend.
This lets you see the dashboard populate with realistic data WITHOUT actual hardware.

USAGE:
  python test_simulate_iot.py

It sends data every second — watch the dashboard update in real time.
Press Ctrl+C to stop.
"""

import time
import math
import random
import requests
import json

BACKEND_URL = "http://localhost:8000"
PATIENT_ID = "patient_01"

def simulate_normal():
    """Normal resting state — slight movement, normal vitals."""
    t = time.time()
    return {
        "ax": round(random.gauss(0.05, 0.02), 3),
        "ay": round(random.gauss(0.02, 0.01), 3),
        "az": round(random.gauss(9.8, 0.05), 3),  # gravity
        "gyro": round(random.gauss(0.5, 0.3), 2),
        "heart_rate": random.randint(68, 78),
        "spo2": random.choice([97, 97, 98, 98, 98, 99]),
        "motion": "normal",
        "distress_sound_detected": False,
        "battery_level": max(0, 87 - int((t % 3600) / 60)),
    }

def simulate_fall():
    """Sudden motion spike simulating a fall."""
    return {
        "ax": round(random.uniform(2.5, 4.0), 3),
        "ay": round(random.uniform(1.5, 3.0), 3),
        "az": round(random.uniform(0.5, 2.0), 3),
        "gyro": round(random.uniform(100, 250), 1),
        "heart_rate": random.randint(95, 130),
        "spo2": random.choice([90, 91, 93, 94]),
        "motion": "sudden",
        "distress_sound_detected": random.choice([True, False]),
        "battery_level": 85,
    }

def simulate_motionless():
    """No movement after fall — inactivity."""
    return {
        "ax": round(random.gauss(0.01, 0.005), 3),
        "ay": round(random.gauss(0.01, 0.005), 3),
        "az": round(random.gauss(0, 0.01), 3),
        "gyro": round(random.gauss(0.1, 0.05), 2),
        "heart_rate": random.randint(50, 60),
        "spo2": random.choice([89, 90, 91]),
        "motion": "none",
        "distress_sound_detected": False,
        "battery_level": 84,
    }

def send_event(data):
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/v1/events/iot/{PATIENT_ID}",
            json=data,
            timeout=2.0,
        )
        result = resp.json()
        return result.get("state", "?"), result.get("fall_score", 0)
    except Exception as e:
        return f"ERROR: {e}", 0

def main():
    print("=" * 60)
    print("  IoT SENSOR SIMULATOR")
    print("=" * 60)
    print()
    print("  Modes:")
    print("    [1] Normal   — 15s of resting data")
    print("    [2] Fall     — 3s spike + 12s motionless")
    print("    [3] Loop     — Continuously alternates 1 & 2")
    print()
    
    mode = input("  Choose mode (1/2/3) [default=3]: ").strip() or "3"
    print()
    
    try:
        if mode == "1":
            print("[SIM] Sending normal data for 15 seconds...")
            for i in range(15):
                data = simulate_normal()
                state, score = send_event(data)
                print(f"  [{i+1:2d}/15] HR={data['heart_rate']} SpO2={data['spo2']} → State={state} Score={score:.2f}")
                time.sleep(1)
                
        elif mode == "2":
            print("[SIM] Simulating a fall event...")
            # Impact
            for i in range(3):
                data = simulate_fall()
                state, score = send_event(data)
                print(f"  [IMPACT {i+1}/3] SMV={math.sqrt(data['ax']**2+data['ay']**2+data['az']**2):.1f}g → State={state} Score={score:.2f}")
                time.sleep(1)
            # Motionless
            for i in range(12):
                data = simulate_motionless()
                state, score = send_event(data)
                print(f"  [STILL  {i+1:2d}/12] HR={data['heart_rate']} SpO2={data['spo2']} → State={state} Score={score:.2f}")
                time.sleep(1)
                
        elif mode == "3":
            cycle = 0
            while True:
                cycle += 1
                print(f"\n--- Cycle {cycle} ---")
                # Normal phase
                print("[SIM] Normal activity (10s)...")
                for i in range(10):
                    data = simulate_normal()
                    state, score = send_event(data)
                    print(f"  [NORMAL {i+1:2d}/10] HR={data['heart_rate']} SpO2={data['spo2']} → {state} ({score:.2f})")
                    time.sleep(1)
                # Fall phase
                print("[SIM] FALL EVENT!")
                for i in range(3):
                    data = simulate_fall()
                    state, score = send_event(data)
                    smv = math.sqrt(data['ax']**2+data['ay']**2+data['az']**2)
                    print(f"  [IMPACT {i+1}/3] SMV={smv:.1f}g → {state} ({score:.2f})")
                    time.sleep(1)
                # Motionless
                print("[SIM] Motionless after fall (15s)...")
                for i in range(15):
                    data = simulate_motionless()
                    state, score = send_event(data)
                    print(f"  [STILL  {i+1:2d}/15] → {state} ({score:.2f})")
                    time.sleep(1)
                    
    except KeyboardInterrupt:
        print("\n\n[DONE] Simulator stopped.")


if __name__ == "__main__":
    main()
