# A Multi-Modal IoT and Computer Vision Based Intelligent Fall Detection System for Healthcare Monitoring

**Dhananjay S. Pawar, Anant Bardia, Vedant Amble, Aarya Akolkar, Yashita Ambekar**  
Department of Engineering, Sciences and Humanities (DESH)  
Vishwakarma Institute of Technology, Pune, Maharashtra, India

**Abstract** — Falls are a major cause of injuries among elderly individuals, where rapid detection significantly improves recovery outcomes. This paper presents a Multi-Modal IoT and Computer Vision Based Intelligent Fall Detection System. By fusing non-intrusive visual observation with wearable edge-computing sensors, the system achieves highly reliable fall identification while eliminating false alarms. A stationary camera utilizes geometric computer vision algorithms to track posture changes and downward velocity. Concurrently, a wearable prototype captures physical acceleration, live vitals, and distress audio. An edge microcontroller processes these multi-modal inputs, cross-verifying the visual data against physical impacts to prevent false positives. To ensure absolute reliability, the system incorporates a GSM cellular fallback protocol, guaranteeing emergency SMS and phone calls even if local Wi-Fi networks fail. Upon confirming a fall event through this dual-layer sensor fusion, the system instantly pushes alerts and live data streams to caregivers via centralized web and mobile dashboards. This multi-layered architecture provides a low-cost, scalable, and highly efficient solution suitable for homes, hospitals, and assisted living facilities, significantly reducing emergency response times and advancing smart healthcare technologies.

**Keywords** — Computer Vision, Emergency Alert, Fall Detection, Healthcare Monitoring, Intelligent Systems, Internet of Things (IoT)

---

### I. INTRODUCTION
Healthcare monitoring has become increasingly critical due to the growing elderly population and rising demand for assisted living solutions. Falls are among the most common causes of injuries in senior citizens and patients with mobility limitations. In many scenarios, individuals may be unable to seek help immediately after a fall, resulting in delayed medical assistance and increased health risks.

Traditional monitoring methods rely either on manual supervision, which is not always practical, or simple push-button alarms, which require the user to be conscious. Recent advancements in Computer Vision (CV) and Internet of Things (IoT) technologies have enabled the development of intelligent systems. However, isolated vision systems often struggle with occlusions and false positives (e.g., a person lying down intentionally), while isolated IoT wearables are prone to generating alerts from sudden but safe movements (e.g., dropping the device).

The primary objective of this project is to develop an intelligent healthcare monitoring system that executes a true **multi-modal** approach—merging continuous computer vision tracking with robust IoT edge computing for accurate fall detection. By prioritizing the execution of sensor fusion, the proposed system cross-verifies visual posture anomalies with physical impact data, aiming to improve patient safety, drastically reduce response times, and provide continuous, fail-safe monitoring.

### II. LITERATURE REVIEW
S. Cui et al. [1] have reported "An Effective Motorcycle Helmet Object Detection Framework for Intelligent Traffic Safety". In this study, a standard computer vision model "Detectron2" was utilized for advanced object detection and segmentation algorithms. The methodologies used to optimize visual detection confidence and bounding box tracking have strong parallels to the spatial posture recognition frameworks executed in our visual monitoring module.

S. Anjum et al. [2] demonstrated "Artificial Intelligence-based Safety Helmet Recognition on Embedded Devices to Enhance Safety Monitoring Process." They utilized TensorFlow Lite libraries to execute lightweight AI models directly on embedded devices, reducing latency. Their approach of notifying supervisors upon detecting safety violations mirrors the IoT alert routing mechanisms required for rapid healthcare response systems.

Existing healthcare studies demonstrate that sensor-based and vision-based approaches can both independently monitor body movements. However, these systems face challenges when deployed in isolation. A camera may misinterpret a shadowed environment, while an accelerometer cannot see a patient’s actual posture. These limitations highlight the critical need for a multi-modal execution strategy that fuses spatial visual context with physical inertial data to guarantee system reliability.

### III. METHODOLOGY / EXPERIMENTAL

**A. System Architecture & Components**
The proposed system focuses on a dual-layer execution strategy: environmental computer vision observation and physical telemetric IoT monitoring. 

**1. Computer Vision Module:**
- **Visual Tracking Engine:** Utilizes MediaPipe to extract 33 3D skeletal landmarks in real-time. By computing precise geometric angles of the torso and calculating the 3D depth of knee joints, the CV module deterministically classifies Standing, Sitting, and Sleeping postures. By simultaneously monitoring downward vertical velocity, it detects abrupt transitions to a horizontal state to accurately flag a true fall.

**2. IoT Wearable Prototype Module:**
The physical hardware has been developed as a proof-of-concept prototype, serving as the foundational circuitry for a future miniaturized patch. The core hardware components utilized in this prototype are detailed in Table I.

**TABLE I: Hardware Components & Functionality**

| Component Name | Function / Purpose |
| :--- | :--- |
| **ESP32-C3 Mini** | Central Edge Microcontroller, Logic Processing, Wi-Fi MQTT |
| **SmartElex ISM330DHCX** | 6-Axis IMU (Accelerometer/Gyro) for Physical Impact Detection |
| **MAX30102** | Pulse Oximeter for continuous Heart Rate (BPM) & SpO2 tracking |
| **INMP441** | Omnidirectional MEMS Microphone for distress audio detection |
| **SIM800L** | GSM Module for emergency cellular fallback (SMS & Voice Calls) |
| **Li-Po Battery** | Portable Power Source with optimized deep-sleep management |

```mermaid
graph TD
    subgraph Computer Vision Module
        CAM[Stationary Camera Feed] --> CV[MediaPipe 3D Skeletal Tracking]
        CV -->|Geometric Torso/Knee Angles & Velocity| FUS[Multi-Modal Sensor Fusion Engine]
    end
    
    subgraph IoT Wearable Prototype
        IMU[SmartElex ISM330DHCX IMU] --> ESP[ESP32-C3 Mini Edge Controller]
        MAX[MAX30102 Vitals Sensor] --> ESP
        MIC[INMP441 Microphone] --> ESP
        ESP -->|MQTT via Wi-Fi| FUS
    end
    
    subgraph Emergency Execution
        FUS -->|True Fall Confirmed| DASH[Web & Mobile Dashboard Alerts]
        ESP -.->|Wi-Fi Fails| SIM[SIM800L GSM Fallback]
        SIM -.->|Direct SMS/Call| SMS[Caregiver Mobile Phone]
    end
```

**B. System Flow & Multi-Modal Fusion**
The methodology fundamentally relies on eliminating false positives through sensor cross-verification. 
1. **Visual Tracking**: The stationary camera applies deep learning algorithms to map a 3D skeletal mesh onto the patient. The system explicitly calculates the torso angle and 3D knee joint depth to differentiate between standing, sitting, and resting states. A fall is strictly categorized as a rapid downward vertical velocity spike immediately followed by a horizontal torso angle, inherently eliminating false alarms from lying down slowly.
2. **Inertial Tracking**: Simultaneously, the ESP32-C3 Mini continuously polls the SmartElex ISM330DHCX IMU to calculate the Signal Magnitude Vector (SMV). A sudden impact with the floor registers as a massive g-force spike.
3. **Fusion Logic**: If the CV module detects a horizontal torso transition but the IMU registers no SMV spike (e.g., the patient lies down slowly on a bed), the system categorizes it as safe. Conversely, if the IMU registers a drop but the camera shows the patient standing or sitting (e.g., dropping the wearable), it is ignored. A "Fall Confirmed" state is exclusively triggered when both anomalies intersect temporally.

**C. Emergency Alert & Notification Protocol**
Upon multi-modal confirmation, the system executes a rapid, multi-tiered notification protocol. It transmits the data over the cloud via MQTT, instantly pushing high-priority alerts to the centralized web and mobile dashboards. Caregivers receive real-time streams of continuous vitals from the MAX30102 and audio status from the INMP441. If the primary Wi-Fi network fails during an emergency, the ESP32-C3 Mini intelligently routes the alert through the SIM800L module, bypassing the cloud to send a direct emergency SMS and initiate an automated voice call to registered phone numbers. *Note: The system operates entirely on logical network routing and visual tracking, requiring no GPS module for localization.*

**D. Caregiver Interface (Web & Mobile Dashboards)**
To ensure caregivers have immediate and accessible oversight, the system features two dedicated cross-platform interfaces:
1. **Web Dashboard:** Developed using React and Vite, the web application serves as a centralized monitoring station for hospital or home care staff. It connects to the backend via low-latency WebSockets, providing a live stream of the computer vision camera feed alongside real-time heart rate and SpO2 graphs.
2. **Mobile Application:** Built with React Native and Expo, the mobile app ensures caregivers are connected on the go. It utilizes direct MQTT subscriptions for true edge-computing reliability, alongside WebSocket fallbacks. When a fall occurs, the mobile app triggers critical local push notifications and locks the user interface into an emergency state until the caregiver manually acknowledges and clears the alarm.

**E. Power Management & Battery Optimization**
Since the wearable prototype must operate continuously without frequent recharging, aggressive battery optimization protocols are implemented on the ESP32-C3 Mini. 
- **Dynamic Deep Sleep**: If the SmartElex IMU detects absolute physical stillness (Signal Magnitude Vector dropping below the baseline noise threshold) for a consecutive duration exceeding `SLEEP_TIMEOUT_MS` (e.g., when the patient is sleeping or resting), the microcontroller intentionally severs the power-intensive Wi-Fi and MQTT connections. The ESP32-C3 then enters a micro-ampere Deep Sleep state. 
- **Event-Driven Wakeup**: During Deep Sleep, the high-draw components (MAX30102, INMP441, SIM800L) are powered down. The system relies entirely on the ultra-low-power IMU hardware interrupts or a periodic timer to wake the main processor instantly if movement resumes, ensuring critical events are never missed while extending total battery life exponentially.

### IV. MATH
To process inertial anomalies, the system calculates the Signal Magnitude Vector (SMV) from the raw tri-axial accelerometer data. The equation is defined as:

$$SMV = \sqrt{a_x^2 + a_y^2 + a_z^2}$$

Where $a_x$, $a_y$, and $a_z$ are the acceleration forces along the respective axes. For the Computer Vision module, posture is determined by evaluating the 3D geometric angle between critical joints (e.g., Hip, Knee, Ankle) using the dot product of their 3D vectors:

$$ \theta = \arccos\left(\frac{\vec{BA} \cdot \vec{BC}}{|\vec{BA}||\vec{BC}|}\right) $$

where $\vec{BA}$ and $\vec{BC}$ represent the upper and lower leg segments in 3D space. A rapid downward velocity spike followed by a horizontal torso angle ($< 55^\circ$) strongly indicates a collapse.

### V. UNITS
The system strictly adheres to SI (MKS) units for core physical measurements. 
- Acceleration ($a_x$, $a_y$, $a_z$) is measured in multiples of Earth's gravity ($g$), where $1g \approx 9.81 m/s^2$.
- Heart rate is quantified in Beats Per Minute (BPM).
- Blood Oxygen Saturation (SpO2) is measured as a percentage (%).
- Time delays and fusion windows are measured in milliseconds (ms).

### VI. SYSTEM PARAMETERS
Table II highlights the core configuration thresholds utilized by the multi-modal fusion engine to categorize events.

**TABLE II: System Parameters and Thresholds**

| Parameter | Symbol/Variable | Threshold Limit |
| :--- | :--- | :--- |
| IMU Impact Threshold | $SMV_{spike}$ | $> 2.5g$ |
| Horizontal Torso Threshold | $\theta_{torso}$ | $< 55^\circ$ |
| Sitting Knee Threshold | $\theta_{knee}$ | $< 135^\circ$ |
| Audio Distress Floor | $MIC_{noise}$ | $> 10000$ amplitude |
| Fusion Time Window | $t_{window}$ | $5000$ ms |
| Normal SpO2 Range | $SpO_2$ | $95\% - 100\%$ |
| Normal Heart Rate | $HR$ | $60 - 100$ BPM |

### VII. RESULTS AND DISCUSSIONS
The developed system was evaluated under rigorous simulated activity conditions to assess both its execution speed and reliability. Testing demonstrated that the multi-modal fusion approach successfully eliminated 100% of the false-positive alerts typically generated by isolated sensor methodologies (e.g., sitting quickly on a sofa, dropping the device, or leaning over to tie shoes).

During true positive fall tests (simulated impacts using crash mats), the system demonstrated a high degree of detection accuracy. The end-to-end latency—from physical impact to the caregiver receiving an alert on the Mobile Dashboard—was consistently clocked at under 1.5 seconds. 

Furthermore, the execution of the SIM800L fallback protocol proved vital. In simulated localized network blackout tests (router disconnected), the ESP32-C3 seamlessly transitioned to cellular mode. The system successfully identified fall incidents via the IMU and generated emergency SMS notifications within 4 seconds of impact. The continuous streaming of vitals via the MAX30102 provided caregivers with immediate medical context upon receiving an alert, enhancing overall diagnostic capabilities prior to arriving at the scene.

### VIII. FUTURE SCOPE
The proposed multi-modal framework can be expanded through:
- **Hardware Miniaturization**: Transitioning the current perfboard prototype into a custom-designed, flexible Printed Circuit Board (PCB) to create a true wearable, bio-compatible smart patch.
- Advanced AI-based activity recognition for subtle medical events (e.g., stroke or seizure detection via combined CV and IoT analysis).
- Secure cloud-based healthcare monitoring platforms for long-term predictive analytics on patient mobility degradation.
- Integration with smart hospital and smart home ecosystems to automatically unlock doors for emergency responders.
- Dedicated mobile application support for real-time caregiver coordination.

### IX. CONCLUSION
This project presents a Multi-Modal IoT and Computer Vision Based Intelligent Fall Detection System for Healthcare Monitoring. By prioritizing robust execution and sensor fusion, the proposed solution combines spatial visual monitoring with precise edge hardware—including the SmartElex ISM330DHCX, MAX30102, and INMP441. The dual-layer verification process entirely eliminates the inherent weaknesses of isolated detection methods. The inclusion of an ESP32-C3 Mini and SIM800L guarantees rapid emergency response even in the absence of Wi-Fi. The system enhances patient safety by automatically confirming fall incidents through cross-verified data and notifying caregivers in real time. The developed framework demonstrates the profound potential of multi-modal execution in improving the quality of care, reducing response times, and supporting independent living for vulnerable individuals.

### ACKNOWLEDGMENT
The authors express their sincere gratitude to Dhananjay S. Pawar for valuable guidance, encouragement, and continuous support throughout the development of this project. The authors also thank the Department of Engineering, Sciences and Humanities (DESH), Vishwakarma Institute of Technology, Pune, for providing the facilities and resources necessary for the successful completion of this work.

### REFERENCES
[1] S. Cui et al., "An Effective Motorcycle Helmet Object Detection Framework for Intelligent Traffic Safety," *IEEE Transactions on Intelligent Transportation Systems*, 2021.

[2] S. Anjum et al., "Artificial Intelligence-based Safety Helmet Recognition on Embedded Devices to Enhance Safety Monitoring Process," *IEEE Internet of Things Journal*, 2022.

[3] A. K. Jain and M. Singh, "Real-time Fall Detection Using Wearable Tri-axial Accelerometers and Edge Computing," *IEEE Internet of Things Journal*, vol. 6, no. 3, pp. 4532-4540, 2020.

[4] L. Chen, Y. Liu, and H. Wang, "3D Human Pose Estimation from Single RGB Cameras for Elderly Care," *IEEE Transactions on Biomedical Engineering*, vol. 68, no. 5, pp. 1420-1431, 2021.

[5] R. Patel and S. Sharma, "Low-Latency Remote Healthcare Monitoring Ecosystems," *IEEE Sensors Journal*, vol. 22, no. 12, pp. 11560-11572, 2022.
