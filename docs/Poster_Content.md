# A Multi-Modal IoT and Computer Vision Based Intelligent Fall Detection System for Healthcare Monitoring

**ASE Project 2**  
**Group no.:** ET -A 3  
**Authors:** Dhananjay S. Pawar, Anant Bardia, Vedant Amble, Aarya Akolkar, Yashita Ambekar  
**Department:** Department of Engineering, Sciences and Humanities (DESH)  
**Section:** ET A

---

## Abstract
This project presents an intelligent Fall Detection System that fuses non-intrusive computer vision, Vision Language Models (VLMs), and wearable IoT sensors. By utilizing a LLaVA VLM to contextualize the environment (differentiating between floor and furniture) and cross-verifying posture changes with physical impact data, it eliminates false alarms. The system also includes GSM cellular fallback to guarantee emergency alerts during Wi-Fi failures.

## Introduction
Falls cause severe injuries in the elderly, and delayed assistance drastically increases health risks. Traditional systems face issues like visual occlusions (cameras) or frequent false positives (wearables misinterpreting intentional resting). This project solves these challenges through a multi-modal approach, fusing continuous visual context, VLM semantic understanding, and physical inertial data to ensure absolute reliability.

## METHODOLOGY
The system operates on a multi-layer execution strategy:
1. **Computer Vision & VLM Module:** Uses MediaPipe for 3D skeletal tracking to classify posture. When a horizontal collapse is detected, a Vision Language Model (LLaVA via Ollama) semantically analyzes the frame to confirm if the person is on the "FLOOR" or "FURNITURE".
2. **IoT Wearable Module:** An ESP32-C3 edge controller processes data from a 6-axis IMU (SmartElex ISM330DHCX) and vitals sensor.
3. **Multi-Modal Fusion:** A fall is exclusively confirmed when the CV module detects a horizontal drop onto the floor (verified by VLM) that temporally intersects with a massive physical impact (SMV spike) from the IMU.

## Block Diagram
**Generation Prompt:** *A high-level technical block diagram of a multi-modal IoT Fall Detection System. The diagram has two primary input nodes: a 'Computer Vision Module' (stationary camera, MediaPipe, and LLaVA VLM) and an 'IoT Wearable Module' (ESP32-C3, IMU, and MAX30102 vitals sensor). Arrows point from both input nodes into a central 'Sensor Fusion Engine'. From the central engine, arrows branch out to 'Web/Mobile Dashboards' via MQTT, with a secondary fallback path labeled 'SIM800L GSM' pointing to a mobile phone icon. Professional, clean, technical blueprint style.*

## Flowchart
**Generation Prompt:** *A software logic flowchart for fall detection. Two parallel start paths: one for 'Camera Feed' and one for 'IMU Data'. The Camera path goes through 'Detect Posture' -> decision diamond 'Is Torso Horizontal?'. If Yes, it proceeds to 'LLaVA VLM: Floor or Furniture?'. The IMU path goes through decision diamond 'Impact SMV Spike Detected?'. Both paths merge at a logical AND gate labeled 'Multi-Modal Fusion'. If both conditions are met simultaneously, an arrow points to 'Dispatch Emergency Alert', with a conditional branch for 'Wi-Fi Offline -> Send GSM SMS'. Clean, modern flowchart aesthetic with distinct shapes.*

## Actual Circuit Design and System
- **Microcontroller:** ESP32-C3 Mini (Edge Logic, Wi-Fi MQTT)
- **IMU:** SmartElex ISM330DHCX (6-Axis Accelerometer/Gyroscope)
- **Vitals Sensor:** MAX30102 (Heart Rate & SpO2 Tracking)
- **Audio:** INMP441 (MEMS Microphone for distress detection)
- **Fallback:** SIM800L (GSM module for SMS/Calls)

## Testing / Implementation
Rigorous testing was conducted using crash mats for true falls and simulated non-fall activities (e.g., tying shoes, sleeping on beds). Upon confirmation, critical alerts and live vitals were pushed to customized React Web and React Native Mobile dashboards.

## Novelty Features/Finding
- **VLM Semantic Contextualization:** Using LLaVA, the system identifies the surface (floor vs. bed) to prevent false positives when users intentionally lie down.
- **Dual-Layer Verification:** Cross-referencing CV/VLM data with physical IoT impacts effectively prevents standard false positives.
- **Fail-Safe Alerting:** SIM800L GSM fallback automatically triggers SMS and phone calls if local Wi-Fi drops.

## Result and Discussion
- **Detection Reliability:** Exhibited robust sensitivity during true fall events while yielding high precision in mitigating false-positive alerts commonly triggered by typical activities of daily living.
- **Dispatch Latency:** The primary MQTT communication layer achieved near real-time end-to-end alert delivery to caregiver dashboards.
- **System Resilience:** Seamless transition to the SIM800L cellular fallback ensured highly reliable emergency SMS dispatch with minimal delay during complete Wi-Fi blackouts.

## Conclusions
By combining spatial visual monitoring, Vision Language Model (VLM) semantic verification, and precise edge hardware, this multi-modal system entirely resolves the weaknesses of isolated fall detection methods. It guarantees rapid, cross-verified emergency response even in the absence of Wi-Fi, dramatically improving patient safety.
