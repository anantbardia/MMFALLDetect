# A Multi-Modal IoT and Computer Vision Fall Detection System Using Vision Language Models and 3D Spatial Tilt Verification

**Dhananjay S. Pawar, Anant Bardia, Vedant Amble, Aarya Akolkar, Yashita Ambekar**  
Department of Engineering, Sciences and Humanities (DESH)  
Vishwakarma Institute of Technology, Pune, Maharashtra, India

**Abstract** — Falls are a major health risk for the elderly, and timely medical response is critical for recovery. However, existing fall detection systems often struggle with reliability when used in isolation. Camera-only systems can detect a person lying down but fail to understand the context—often triggering false alarms when a person simply lies on a bed. Conversely, standalone wearable sensors are prone to false positives caused by everyday activities like bumping into a table or rapid arm movements. This paper presents a prototype multi-modal fall detection system designed to address these specific weaknesses by combining computer vision with an IoT wearable device. The vision module uses MediaPipe for skeletal tracking and queries a locally hosted Vision Language Model (LLaVA) to semantically distinguish between a person on the floor versus on furniture. Simultaneously, the ESP32-based wearable module utilizes a 3D Spatial Tilt algorithm to verify whether a physical impact actually resulted in a change in body orientation. A backend engine fuses both data streams using a weighted scoring model. To ensure reliability during Wi-Fi outages, the system includes a GSM cellular fallback module for SMS and voice alerts. Laboratory testing demonstrated that cross-verifying geometric vision with semantic VLM understanding and physical inertial data effectively filters out the false positives that commonly trigger single-modality systems.

**Keywords** — Fall Detection, Computer Vision, Vision Language Models (VLM), Internet of Things (IoT), Sensor Fusion, Edge Computing, Healthcare Monitoring.

---

### I. INTRODUCTION

As the global population ages, the demand for assisted living technologies and remote healthcare monitoring continues to grow. For elderly individuals living alone, a fall is a critical medical event. If a person is injured or falls unconscious and cannot call for help, the resulting delay in medical attention can lead to severe complications. Automated fall detection systems aim to solve this by immediately alerting caregivers, but wide-scale adoption has been hindered by a persistent issue: false alarms. 

Current fall detection systems generally rely on either cameras or wearable sensors, and both have fundamental limitations.

**The Context Problem in Vision:** A camera can mathematically track a person's posture and detect when they transition from standing to lying down. However, geometry alone lacks context. To a standard computer vision algorithm, collapsing onto the floor and lying down on a sofa look geometrically identical. This leads to chronic false positives in home environments.

**The Noise Problem in Wearables:** Wearable sensors (like smartwatches or pendants) use accelerometers to detect the physical impact of a fall. However, human hands and arms experience high acceleration during normal daily activities—such as clapping, tossing a phone on a desk, or waving. Using a simple acceleration threshold to detect falls results in a system that cries wolf too often, eventually leading to alert fatigue for caregivers.

**The Network Problem:** Most smart home healthcare systems rely on Wi-Fi and cloud servers to process data and send alerts. If the internet goes down, the system becomes useless—a dangerous single point of failure.

This paper details the design and implementation of a prototype system built to address these three problems. It combines a stationary camera with a custom-built wearable IoT module. To solve the camera's context problem, we integrated a Vision Language Model (LLaVA) to semantically analyze the room and determine what the person is lying on. To solve the wearable's noise problem, we developed a multi-phase state machine that checks for a physical change in body orientation using a 3D Spatial Tilt algorithm. Finally, the system includes a GSM cellular module to guarantee alerts are sent even if the local Wi-Fi fails.

### II. RELATED WORK

The challenge of reliable fall detection has been extensively explored in literature, typically divided by the sensing modality used.

**Camera-Based Systems:** Early vision-based systems relied on background subtraction and bounding box aspect ratios to detect falls [1]. More recently, skeletal tracking frameworks like OpenPose and MediaPipe have become the standard, allowing systems to calculate joint angles to estimate posture. However, as noted by Rougier et al. [4], while shape deformation and posture tracking are effective for detecting a horizontal state, they struggle with disambiguating intentional resting from accidental falls without additional context. 

**Wearable Systems:** Accelerometer-based detection is widely used due to its low cost and privacy-preserving nature [2]. However, Casilari et al. [3] benchmarked several public datasets and highlighted the difficulty of distinguishing falls from vigorous Activities of Daily Living (ADLs) using inertial data alone. Simple thresholding is insufficient, leading researchers to explore complex machine learning models (e.g., SVMs, Decision Trees) on wearable edge devices [5].

**Multimodal and VLM Approaches:** To overcome the limitations of single sensors, recent research has shifted toward multimodal fusion. Liu et al. [6] introduced LLaVA, a multimodal model connecting a vision encoder with a large language model, demonstrating strong visual question-answering capabilities. Ferro et al. [7] presented REMONI, a system integrating wearable devices with multimodal LLMs for remote health monitoring. Our work builds on these concepts by applying a VLM specifically as a semantic verification layer for fall detection, paired with a physical orientation-checking wearable.

### III. SYSTEM ARCHITECTURE

The proposed architecture is divided into three cooperating subsystems: the Camera & VLM Module, the IoT Wearable Module, and the Centralized Backend Fusion Engine. 

#### A. Hardware Components
The prototype was built using readily available hardware components to demonstrate the feasibility of the edge-computing logic:
*   **Stationary Camera:** Standard webcam connected to a local processing node.
*   **ESP32-C3 Mini:** The core microcontroller for the wearable, chosen for its built-in Wi-Fi and small footprint.
*   **SmartElex ISM330DHCX:** A high-precision 6-axis IMU (accelerometer and gyroscope) used for detecting impacts, free-fall, and body orientation.
*   **MAX30102:** A pulse oximetry and heart-rate sensor to monitor vital signs.
*   **INMP441:** An I2S MEMS microphone for detecting audio distress signals.
*   **SIM800L:** A GSM/GPRS module used exclusively as an emergency cellular fallback.

#### B. Architectural Flow
The system operates asynchronously. The camera module tracks posture continuously. If a potential fall is detected visually, it queries the VLM. Independently, the wearable module monitors physics data; if an impact occurs, it evaluates its internal state machine. Both modules transmit their confidence scores via MQTT to the central backend. The backend calculates a weighted score and, if a fall is confirmed, routes alerts to caregiver web and mobile dashboards. 

### IV. COMPUTER VISION AND VLM MODULE

The vision module operates in two stages: geometric tracking (fast, runs every frame) and semantic verification (slower, runs only when needed).

#### 1. Geometric Skeletal Tracking
We use Google's MediaPipe Pose to extract 33 3D skeletal landmarks from the video feed. By calculating the angles between the shoulders, hips, and knees, the system classifies the person's current posture (Standing, Sitting, Bending, or Horizontal). 

Because raw landmark data can be noisy and jittery, we apply an Exponential Moving Average (EMA) filter to the calculated joint angles:
$$ \theta_{smoothed} = \alpha \cdot \theta_{current} + (1 - \alpha) \cdot \theta_{previous} $$
This smoothing prevents single frames of bad tracking from causing the posture state to flicker rapidly. The system requires the calculated posture to remain "Horizontal" for a set number of consecutive frames before it considers it a potential fall. 

#### 2. Semantic Verification via VLM
Once a stable horizontal posture is detected, the system hits its primary limitation: is the person on the floor or in bed? To answer this, the system captures a frame and sends it to a locally hosted instance of LLaVA (running via Ollama). 

The system prompts the VLM with a specific question regarding the scene context. The VLM acts as a semantic classifier, returning whether the surface beneath the person is "FLOOR" or "FURNITURE". Because LLMs can sometimes hallucinate or give inconsistent answers on edge cases, we implemented a temporal voting mechanism. The system queries the VLM across multiple frames; only if a majority of the responses classify the surface as "FLOOR" does the vision module officially flag a fall.

### V. IOT WEARABLE MODULE

The wearable device is worn on the wrist. Because wrists move erratically, we abandoned simple acceleration thresholds in favor of a **Multi-Phase Authentic Fall State Machine**. To trigger a fall alert, the sensor data must pass four sequential checks. If any check fails, the event is discarded as a normal activity.

#### 1. Phase 1: Free-Fall Prerequisite
A genuine fall involves gravity. Before a person hits the ground, their body experiences a brief period of near-zero g-force. Banging a hand on a table or dropping the device generally does not produce this specific signature. The IMU must register a distinct free-fall event before it even begins looking for an impact.

#### 2. Phase 2: Impact and Timing Gate
Following the free-fall, the system looks for an acceleration spike indicating an impact ($SMV = \sqrt{a_x^2 + a_y^2 + a_z^2}$). However, the timing between the free-fall and the impact must align with human physics. If the impact happens too quickly, it's likely an arm swing. If it takes too long, it wasn't a continuous fall.

#### 3. Phase 3: 3D Spatial Tilt Verification
This is the core physical verification. The ESP32 maintains a smoothed "pre-fall" gravity vector representing how the arm was oriented before the event. After the impact, it waits for the sensor to settle and records a "post-fall" gravity vector. 
By calculating the dot-product between these two vectors, the system finds the angular change in the body's orientation:
$$ \cos(\theta_{tilt}) = \frac{\vec{V}_{pre} \cdot \vec{V}_{post}}{|\vec{V}_{pre}||\vec{V}_{post}|} $$
If a person slaps a table, their hand ends up in roughly the same orientation it started in (low tilt angle). If a person collapses to the floor, their overall orientation changes significantly (high tilt angle). A secondary gyroscopic check ensures rotational tumbling occurred.

#### 4. Phase 4: Post-Impact Inactivity
Finally, if a person trips but catches themselves, they will immediately resume moving. The system requires a period of physical stillness following the impact to confirm the person is incapacitated or resting on the floor. 

#### Vital Sign Verification
The module also includes a MAX30102 sensor. To ensure it doesn't read false heart rates when pressed against a pillow or table, it uses a differential optical heuristic. Human blood absorbs red light heavily but reflects infrared (IR) light. Inanimate objects reflect both similarly. The sensor checks this Red/IR ratio to verify it is actually touching human skin before transmitting vitals.

### VI. FUSION ENGINE AND NETWORK RESILIENCE

#### A. Weighted Scoring Fusion
The backend server receives data from both the camera and the wearable via MQTT. It fuses these inputs using a weighted scoring formula:
$$ FallScore = W_{CV} \cdot S_{CV} + W_{Motion} \cdot S_{Motion} + W_{Inactivity} \cdot S_{Inactivity} + W_{Audio} \cdot S_{Audio} $$
Each variable ($S$) is a normalized confidence score (0 to 1), and each weight ($W$) is an adjustable parameter that sums to 1. 

This approach allows for graceful degradation. If the camera is blinded or the person walks out of the frame, the wearable's motion and inactivity scores can still trigger an alert if they are high enough. Conversely, if the wearable battery dies, a highly confident CV+VLM detection can still raise an alarm.

#### B. GSM Cellular Fallback
Standard IoT devices fail silently if the local Wi-Fi router loses power or internet connectivity. To solve this, the ESP32 actively monitors its MQTT connection. If the connection drops and a fall is detected by the on-device state machine, the ESP32 powers up the SIM800L module. It bypasses the cloud entirely, sending a hardcoded SMS message and placing an automated phone call directly to the caregiver's cell phone over the GSM cellular network.

### VII. SYSTEM EVALUATION AND RESULTS

The prototype was evaluated in a controlled laboratory environment. Testing involved volunteers performing simulated falls onto crash mats, alongside a variety of non-fall activities (Activities of Daily Living) designed to trick the sensors, such as rapid sitting, tossing the wearable, clapping, and deliberately lying down on beds.

#### A. Event Logging and Latency
During the testing sessions, the backend system recorded all state transitions to a local SQLite database. By analyzing these logs, we extracted the backend processing latency—the time between the server receiving a sensor trigger and dispatching an alert to the web dashboard.

**TABLE II: Measured Backend Processing Latency**

| Trigger Pathway | Alert Escalation | Measured Latency |
| :--- | :--- | :--- |
| Camera (CV+VLM) | Fall Alert Sent | 10.7 – 18.1 ms |
| Camera (CV+VLM) | Emergency Alert | 13.3 – 18.1 ms |

The camera-triggered alerts showed extremely low server-side latency (<20ms). This is because the heavy lifting—the skeletal tracking and the VLM image inference—is processed locally on the vision node before the event is sent to the backend. 

When the IoT wearable independently confirms a fall, it has already waited through its required "post-impact inactivity" phase on the device itself. Therefore, when the server receives a "hardware-confirmed" MQTT packet, it bypasses the fusion scoring and immediately dispatches the alert. 

*Note: The latencies in Table II reflect server-processing time only. Total real-world latency from the moment a body hits the floor to a caregiver's phone buzzing also includes VLM inference time (~1-3 seconds depending on GPU), MQTT transport time, and push notification delivery.*

#### B. Qualitative Observations

**Vision Performance:** The integration of the VLM successfully solved the context problem during lab tests. When volunteers intentionally lay down on a bed, the geometric tracker flagged a horizontal posture, but the VLM correctly classified the surface as "FURNITURE" and suppressed the alarm. The primary failure mode of standard camera systems was effectively mitigated.

**Wearable Performance:** The Multi-Phase State Machine successfully filtered out erratic wrist movements. When volunteers struck a table or dropped the device, the system recognized the lack of free-fall or the lack of a 3D orientation change, and correctly ignored the events.

**Network Resilience:** In tests where the Wi-Fi router was intentionally unplugged, the ESP32 successfully detected the network timeout, powered the SIM800L, and sent the fallback SMS. This pathway introduces significant latency (connecting to a cellular tower and sending an SMS can take 10-20 seconds), but guarantees delivery when the primary fast-path is down.

#### C. Limitations
The system is currently a prototype tested in a controlled environment with healthy volunteers simulating falls. Clinical trials with elderly participants in real-world home environments are necessary to determine accurate sensitivity, specificity, and false-discovery rates. Furthermore, running a VLM locally requires specialized hardware (a discrete GPU or an AI accelerator like an NPU) on the vision node, which increases the upfront cost of the system compared to simple IP cameras. The GSM fallback is also strictly dependent on local cellular reception.

### VIII. FUTURE WORK

Future iterations of this project will focus on hardware miniaturization. The ESP32 and IMU components used in this prototype are somewhat bulky for a wrist-worn device; transitioning to a custom-designed PCB and a bio-compatible patch form-factor would improve patient comfort and compliance. 

On the software side, the capabilities of the Vision Language Model can be expanded. Rather than just verifying falls after they happen, the VLM could periodically analyze the room to identify environmental hazards (e.g., loose rugs, spills) and proactively warn caregivers of a high fall risk.

### IX. CONCLUSION

This paper presented a multi-modal fall detection system designed to fix the specific flaws of standalone cameras and wearables. By combining geometric posture tracking with the semantic understanding of a Vision Language Model, the system can differentiate between collapsing on the floor and resting on furniture. By utilizing a Multi-Phase State Machine and a 3D Spatial Tilt algorithm, the wearable module verifies physical orientation changes, filtering out the noise of everyday arm movements. A centralized engine fuses these inputs, while a GSM fallback ensures alerts are delivered even during internet outages. Laboratory testing of the prototype demonstrated that this cross-verifying, multi-modal approach yields a more robust and context-aware monitoring system, offering a practical path forward for reliable elderly care technology.

### ACKNOWLEDGMENT
The authors express their sincere gratitude to Dhananjay S. Pawar for valuable guidance, encouragement, and continuous support. We also thank the Department of Engineering, Sciences and Humanities (DESH), Vishwakarma Institute of Technology, Pune.

### REFERENCES
[1] M. Mubashir, L. Shao, and L. Seed, "A survey on fall detection: Principles and approaches," *Neurocomputing*, vol. 100, pp. 144–152, 2013.
[2] N. Noury et al., "Fall detection — Principles and methods," in *Proc. 29th Annual IEEE EMBC*, pp. 1663–1666, 2007.
[3] E. Casilari, J. A. Santoyo-Ramón, and J. M. Cano-García, "Analysis of public datasets for wearable fall detection systems," *Sensors*, vol. 17, no. 7, p. 1513, 2017.
[4] C. Rougier et al., "Robust video surveillance for fall detection based on human shape deformation," *IEEE Trans. Circuits Syst. Video Technol.*, vol. 21, no. 5, pp. 611–622, 2011.
[5] N. Lu, T. Wang, J. Yang, and E. A. Krupinski, "Wearable healthcare sensor system for IMU-based remote fall detection," *IEEE Access*, vol. 8, pp. 54391–54404, 2020.
[6] H. Liu, C. Li, Q. Wu, and Y. J. Lee, "Visual Instruction Tuning," in *Proc. NeurIPS*, 2023.
[7] S. Ferro et al., "REMONI: An Autonomous System Integrating Wearables and Multimodal Large Language Models for Enhanced Remote Health Monitoring," in *Proc. IEEE International Symposium on Medical Measurements and Applications (MeMeA)*, 2024.
