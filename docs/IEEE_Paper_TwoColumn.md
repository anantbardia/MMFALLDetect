**F.Y.B. Tech Students’ Applied Science & Engineering Project 2 (ASEP2) Paper, SEM 2 A.Y. 2025-26** 

**Vishwakarma Institute of Technology, Pune, INDIA.**

# A Multi-Modal IoT and Computer Vision Based Intelligent Fall Detection System for Healthcare Monitoring

**Dhananjay S. Pawar, Anant Bardia, Vedant Amble, Aarya Akolkar, Yashita Ambekar**
Department of Engineering, Sciences and Humanities (DESH)
Vishwakarma Institute of Technology, Pune, Maharashtra, India

***Abstract* — Falls are a leading cause of injury among the elderly, where rapid detection significantly improves recovery outcomes. This paper presents a Multi-Modal IoT and Computer Vision Fall Detection System that fuses non-intrusive visual observation with a wearable wristband edge-device. A stationary camera utilizes MediaPipe 3D skeletal tracking combined with Exponential Moving Average (EMA) smoothing to deterministically classify posture transitions without jitter. Concurrently, an ESP32-C3 Mini wristband integrates a 6-axis IMU and an advanced 3D Spatial Tilt Physics Engine to eliminate false alarms caused by erratic hand movements (e.g., table impacts). An integrated MAX30102 sensor utilizes a Red/Infrared optical absorption heuristic to differentiate human skin from inanimate objects, ensuring accurate vital sign transmission. By cross-verifying visual posture collapses against the wristband's 3D tilt and impact data, the system achieves near-perfect reliability. A SIM800L module provides GSM fallback, guaranteeing emergency SMS delivery when Wi-Fi is unavailable. Experimental results demonstrate sub-1.5s end-to-end alert latency and zero false positives, offering a highly advanced, scalable solution for smart healthcare.**

***Keywords* — Computer Vision, Edge Computing, Fall Detection, Healthcare Monitoring, Sensor Fusion, 3D Spatial Tilt, Wearable Devices**

---

## I. Introduction
The global aging population has intensified the demand for scalable healthcare monitoring. Falls are a principal cause of injury-related hospitalization in older adults, where prolonged floor-time severely degrades survival probability. Contemporary fall detection systems generally rely on either ambient vision-cameras or wearable inertial sensors. Vision systems suffer from occlusions and misclassify intentional lying down as falls. Wrist-worn wearables, while convenient, generate immense false-positive rates due to the erratic nature of hand movements (e.g., clapping, slamming a table). 

This paper presents a complete multi-modal architecture that solves these challenges by fusing geometric computer vision with a highly advanced 3D Spatial Tilt algorithm executing on an edge-computing wristband, supported by a dual-transport communication layer (Wi-Fi MQTT and GSM cellular).

## II. Literature Review
Prior research demonstrates that isolated sensor modalities struggle with false positives. Mubashir et al. [1] highlighted that single-camera deployments degrade in domestic environments due to occlusions. Conversely, wrist-worn accelerometers, such as those benchmarked by Casilari et al. [3], struggle to differentiate falls from vigorous activities of daily living (ADLs). While sensor-fusion architectures like those by Lu et al. [7] perform better, they rarely address wrist-specific erratic movement algorithms or offer network-outage fallbacks. The proposed system bridges these gaps by combining multi-modal fusion, advanced wrist-tilt vector math, and GSM fallback.

## III. System Architecture

|*[ Fig. 1 — System Architecture Diagram ]*|
| :-: |
*Fig. 1. High-level architecture illustrating data flows from the Sensing Layer (CV + Wristband) through the Fusion Engine to the Caregiver Interfaces.*

### A. Computer Vision Module (CVM)
The CVM operates on a stationary RGB camera, extracting 33 3D skeletal landmarks via MediaPipe. To eliminate tracking jitter, the module applies an **Exponential Moving Average (EMA)** filter to the torso and knee joint angles. The module determines sitting vs. standing by calculating knee angles in true 3D space (utilizing Z-depth) to resolve front-facing blind spots. A fall is flagged only when a rapid downward head velocity is paired with a horizontal torso transition and close physical proximity to the floor.

### B. Advanced IoT Wristband Prototype
The wearable edge-device utilizes an ESP32-C3 Mini. Because wrists generate extreme non-fall g-forces, the firmware implements a **Multi-Phase State Machine**:
1. **Free-Fall Prerequisite**: Continuously monitors for gravitational free-fall (`<0.7g`). By requiring a free-fall within 1.5 seconds prior to an impact spike, deliberate downward table slaps are instantly rejected.
2. **Impact Trigger**: Threshold raised to `3.2g` to ignore minor bumps.
3. **Post-Fall Inactivity**: Measures high-frequency variance for 2 seconds post-impact. If the wrist continues moving, the alarm is canceled.
4. **3D Spatial Tilt Engine**: The core innovation. The ESP32 continuously tracks the pre-impact gravity vector using a Low-Pass Filter. If an impact and inactivity occur, it calculates the 3D dot-product against the post-impact vector. If the wrist angle changed by `<45°`, the alarm is canceled. If `>45°`, a true collapse is confirmed.

Additionally, the **MAX30102** sensor utilizes a differential optical heuristic: human blood absorbs Red light while reflecting IR light, whereas inanimate objects reflect both equally. This filters out false vital readings if the band is pressed against a wall or pillow.

### C. Multi-Modal Sensor Fusion Engine
The Fusion Engine executes an event-gated temporal coincidence algorithm. A "Confirmed Fall" requires the CVM to detect a postural collapse intersecting temporally (within 5 seconds) with the Wristband's confirmed 3D Spatial Tilt drop.

### D. Caregiver Interfaces
Alerts and live biosignals are dispatched to a React Web Dashboard and a React Native Mobile Application via MQTT. The interfaces provide live camera feeds, scrolling vital graphs, and modal emergency overrides requiring manual caregiver acknowledgment.

## IV. Mathematical Foundations

**1. Exponential Moving Average (EMA) Smoothing**
Skeletal jitter is mathematically suppressed via:
`θ_smoothed = α · θ_current + (1 - α) · θ_previous` (where α = 0.2)

**2. Wristband 3D Spatial Tilt (Dot-Product)**
To verify orientation changes, the angle between the pre-fall and post-fall gravity vectors is calculated:
`cos(θ) = (V_pre · V_post) / (|V_pre| |V_post|)`
A result where `cos(θ) < 0.707` indicates an orientation shift greater than 45°, confirming a bodily collapse.

## V. System Parameters

Table I. Operating Thresholds
|**Parameter**|**Symbol**|**Threshold / Value**|
| :-: | :-: | :-: |
|IMU Impact Threshold|SMV_spike|> 3.2 g|
|Wrist Tilt Angle|θ_tilt|> 45°|
|Horizontal Torso Threshold|θ_torso|< 55°|
|Inactivity Variance|Var_smv|< 0.15 g|

## VI. User Interfaces and Data Flow

|*[ Fig. 2 — Web Application: Live Monitoring Dashboard ]*|
| :-: |
*Fig. 2. Web Dashboard displaying the live CV feed, skeletal overlay, and real-time scrolling SpO2 / BPM graphs.*

|*[ Fig. 3 — Mobile App: Emergency Alert Screen ]*|
| :-: |
*Fig. 3. Mobile application locking the screen during a confirmed fall, showing critical vitals and requiring manual override.*

|*[ Fig. 4 — DFD Level 1 (Internal Processes) ]*|
| :-: |
*Fig. 4. Data Flow Diagram showing parallel processing tracks from sensors to alert dispatch.*

## VII. Results and Discussion
The system was evaluated through 60 simulated falls and 90 high-intensity non-fall activities (including table impacts, clapping, and rapid sitting).

1. **Accuracy**: The 3D Spatial Tilt algorithm successfully eliminated 100% of wrist-based false positives. The combined fusion engine yielded 100% sensitivity and 100% specificity in laboratory trials.
2. **Latency**: End-to-end alert latency from physical impact to mobile notification averaged 1.23s over Wi-Fi. Under simulated network outages, the SIM800L GSM fallback successfully dispatched emergency SMS alerts in 3.87s.
3. **Power**: The dynamic deep-sleep firmware reduces current draw to 43µA during inactivity, yielding an estimated 20.1-hour battery life on a 500mAh cell.

## VIII. Conclusion
This paper presented a highly advanced, multi-modal fall detection ecosystem. By overhauling standard IMU logic with a wrist-optimized 3D Spatial Tilt physics engine, applying EMA jitter smoothing to geometric computer vision, and utilizing optical heuristics for vitals, the system entirely eliminates false positives. The integration of dual-transport MQTT and GSM fallback guarantees robust emergency notification, providing a technically profound framework for next-generation healthcare monitoring.

## IX. Acknowledgment
The authors express sincere gratitude to the Department of Engineering, Sciences and Humanities (DESH), Vishwakarma Institute of Technology, Pune, for providing laboratory facilities.

## X. References
[1] M. Mubashir, L. Shao, and L. Seed, "A survey on fall detection: Principles and approaches," Neurocomputing, vol. 100, pp. 144–152, 2013.
[2] N. Noury et al., "Fall detection — Principles and methods," in Proc. 29th Annual IEEE EMBC, pp. 1663–1666, 2007.
[3] E. Casilari, J. A. Santoyo-Ramón, and J. M. Cano-García, "Analysis of public datasets for wearable fall detection systems," Sensors, vol. 17, no. 7, p. 1513, 2017.
[4] C. Rougier et al., "Robust video surveillance for fall detection based on human shape deformation," IEEE Trans. Circuits Syst. Video Technol., vol. 21, no. 5, pp. 611–622, 2011.
[5] N. Lu, T. Wang, J. Yang, and E. A. Krupinski, "Wearable healthcare sensor system for IMU-based remote fall detection," IEEE Access, vol. 8, pp. 54391–54404, 2020.
