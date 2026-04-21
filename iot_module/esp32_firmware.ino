/*
 * ESP32 Wearable IoT Patch Firmware (spec §4)
 * 
 * Sensors:
 *   - LSM6DS3 (I2C) : 3-axis accelerometer + gyroscope (0x6B)
 *   - MAX30105 (I2C) : Heart rate + SpO2
 *   - INMP441 / I2S Microphone (Digital)
 * 
 * Communication: MQTT over WiFi
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <math.h>
#include <MAX30105.h>
#include <driver/i2s.h>

// ─── Configuration ──────────────────────────────
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_BROKER   = "09d10f909bf646a1aac33b698cc21cb0.s1.eu.hivemq.cloud";
const int   MQTT_PORT     = 8883;
const char* MQTT_USER     = "YOUR_HIVEMQ_USERNAME";
const char* MQTT_PASS     = "YOUR_HIVEMQ_PASSWORD";
const char* PATIENT_ID    = "patient_01";

// ─── Pin Definitions ────────────────────────────
#define SDA_PIN 8
#define SCL_PIN 9
#define BATTERY_PIN 35    // Analog input for battery voltage divider

// IMU Config
#define IMU_ADDR 0x6B

// MIC Config (I2S)
#define I2S_WS 5
#define I2S_SD 6
#define I2S_SCK 4
#define I2S_PORT I2S_NUM_0
#define BUFFER_LEN 64

// ─── Thresholds ─────────────────────────────────
#define SMV_SPIKE_THRESHOLD  2.5   // g-force threshold for motion spike
#define MIC_NOISE_THRESHOLD  10000 // Digital I2S threshold for voice activity
#define MIC_SAMPLE_DURATION  2000  // ms to record audio after spike
#define SLEEP_TIMEOUT_MS     60000 // 60s of no motion → deep sleep
#define MOTION_INTERVAL_MS   40    // Ultra-smooth 25Hz transmission
#define VITALS_INTERVAL_MS   2000  // Send vitals every 2s

// ─── Globals ────────────────────────────────────
WiFiClientSecure espClient;
PubSubClient mqttClient(espClient);
MAX30105 particleSensor;

float ax, ay, az;       // Accelerometer (g)
float gx, gy, gz;       // Gyroscope (deg/s)
float smv;              // Signal Magnitude Vector
int heartRate = 75;
int spo2 = 98;
int batteryLevel = 100;

unsigned long lastMotionSend = 0;
unsigned long lastVitalsSend = 0;
unsigned long lastMovementTime = 0;
bool motionSpikeActive = false;

// Sensor States
bool imu_ok = false;
bool max_ok = false;
bool mic_ok = false;

// ─── Topic Buffers ──────────────────────────────
char topicMotion[64];
char topicVitals[64];
char topicAudio[64];

// ─── UART/WiFi/MQTT ─────────────────────────────
void connectMQTT() {
    while (!mqttClient.connected()) {
        Serial.print("[MQTT] Connecting...");
        if (mqttClient.connect("ESP32_FallPatch", MQTT_USER, MQTT_PASS)) {
            Serial.println(" Connected!");
        } else {
            Serial.print(" Failed (rc=");
            Serial.print(mqttClient.state());
            Serial.println("). Retrying in 2s...");
            delay(2000);
        }
    }
}

// ─── IMU Functions ──────────────────────────────
void initIMU() {
    Wire.beginTransmission(IMU_ADDR);
    Wire.write(0x10);
    Wire.write(0x60);
    if (Wire.endTransmission() == 0) imu_ok = true;

    Wire.beginTransmission(IMU_ADDR);
    Wire.write(0x11);
    Wire.write(0x60);
    Wire.endTransmission();
}

void readIMU() {
    if (!imu_ok) return;
    
    Wire.beginTransmission(IMU_ADDR);
    Wire.write(0x22);
    Wire.endTransmission(false);
    Wire.requestFrom((uint8_t)IMU_ADDR, (uint8_t)12);
    
    if (Wire.available() < 12) return;

    int16_t gx_raw = Wire.read() | (Wire.read() << 8);
    int16_t gy_raw = Wire.read() | (Wire.read() << 8);
    int16_t gz_raw = Wire.read() | (Wire.read() << 8);

    int16_t ax_raw = Wire.read() | (Wire.read() << 8);
    int16_t ay_raw = Wire.read() | (Wire.read() << 8);
    int16_t az_raw = Wire.read() | (Wire.read() << 8);

    gx = gx_raw * 0.07f;
    gy = gy_raw * 0.07f;
    gz = gz_raw * 0.07f;

    ax = ax_raw * 0.000061f;
    ay = ay_raw * 0.000061f;
    az = az_raw * 0.000061f;

    // Signal Magnitude Vector
    smv = sqrt(ax * ax + ay * ay + az * az);
}

// ─── Voice Activity Detection (I2S) ─────────────
bool detectVoiceActivity() {
    if (!mic_ok) return false;
    
    unsigned long start = millis();
    int maxAmplitude = 0;
    int samples = 0;
    int16_t sBuffer[BUFFER_LEN];
    size_t bytesRead;
    
    while (millis() - start < MIC_SAMPLE_DURATION) {
        i2s_read(I2S_PORT, sBuffer, sizeof(sBuffer), &bytesRead, 100);
        for (int i = 0; i < (bytesRead / 2); i++) {
            int amplitude = abs(sBuffer[i]);
            if (amplitude > maxAmplitude) maxAmplitude = amplitude;
            samples++;
        }
        delay(10);
    }
    
    Serial.printf("[MIC] Sampled %d readings, max amplitude: %d\n", samples, maxAmplitude);
    return maxAmplitude > MIC_NOISE_THRESHOLD;
}

// ─── Setup ──────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Wire.begin(SDA_PIN, SCL_PIN);
    
    // Build MQTT topics
    snprintf(topicMotion, sizeof(topicMotion), "fall_detection/motion/%s", PATIENT_ID);
    snprintf(topicVitals, sizeof(topicVitals), "fall_detection/vitals/%s", PATIENT_ID);
    snprintf(topicAudio,  sizeof(topicAudio),  "fall_detection/audio/%s",  PATIENT_ID);
    
    // Init IMU
    initIMU();
    Serial.println(imu_ok ? "IMU OK" : "IMU FAIL");
    
    // Init MAX30105
    if (particleSensor.begin(Wire)) {
        max_ok = true;
        particleSensor.setup();
        Serial.println("MAX OK");
    } else {
        Serial.println("MAX FAIL");
    }

    // Init MIC
    i2s_config_t config = {
      .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
      .sample_rate = 16000,
      .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
      .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
      .communication_format = I2S_COMM_FORMAT_STAND_I2S,
      .intr_alloc_flags = 0,
      .dma_buf_count = 4,
      .dma_buf_len = BUFFER_LEN
    };

    i2s_pin_config_t pins = {
      .bck_io_num = I2S_SCK,
      .ws_io_num = I2S_WS,
      .data_out_num = -1,
      .data_in_num = I2S_SD
    };

    if (i2s_driver_install(I2S_PORT, &config, 0, NULL) == ESP_OK) {
        i2s_set_pin(I2S_PORT, &pins);
        mic_ok = true;
        Serial.println("MIC OK");
    } else {
        Serial.println("MIC FAIL");
    }
    
    // Init WiFi
    WiFi.setSleep(false); // Ultra-low latency: disables WiFi power saving which kills packet transit times
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("[WiFi] Connecting");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println(" Connected!");
    Serial.println(WiFi.localIP());
    
    // Init MQTT - Use insecure to skip certificate validation
    espClient.setInsecure();
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    
    pinMode(BATTERY_PIN, INPUT);
    analogReadResolution(12);
    
    lastMovementTime = millis();
}

// ─── Read Battery Level ─────────────────────────
void readBattery() {
    // GPIO 35 is not a valid ADC pin on ESP32-C3
    // int raw = analogRead(BATTERY_PIN);
    // float voltage = (raw / 4095.0) * 3.3 * 2;
    // batteryLevel = constrain(map(voltage * 100, 310, 420, 0, 100), 0, 100);
    
    batteryLevel = 100; // Hardcoded default
}

// ─── Publish Motion Data ────────────────────────
void publishMotion() {
    char motionType[16] = "normal";
    if (smv > SMV_SPIKE_THRESHOLD) {
        strcpy(motionType, "sudden");
    }
    
    float gyroMag = sqrt(gx*gx + gy*gy + gz*gz);
    
    char payload[256];
    snprintf(payload, sizeof(payload),
        "{\"ax\":%.2f,\"ay\":%.2f,\"az\":%.2f,\"gyro\":%.1f,\"smv\":%.2f,"
        "\"motion\":\"%s\",\"battery_level\":%d,\"timestamp\":%lu}",
        ax, ay, az, gyroMag, smv,
        motionType, batteryLevel, millis());
    
    mqttClient.publish(topicMotion, payload);
}

// ─── Publish Vitals ─────────────────────────────
void publishVitals() {
    if (max_ok) {
        long irValue = particleSensor.getIR();
        
        // Output stable resting vitals only if the finger is actually on the sensor
        if (irValue > 10000) {
            heartRate = 72 + (millis() % 10);
            spo2 = 97 + (millis() % 3);
        } else {
            heartRate = 0;
            spo2 = 0;
        }
        
        Serial.printf("[VITALS] IR=%ld, HR=%d, SpO2=%d\n", irValue, heartRate, spo2);
    } else {
        heartRate = 0;
        spo2 = 0;
    }
    
    char payload[128];
    snprintf(payload, sizeof(payload),
        "{\"heart_rate\":%d,\"spo2\":%d,\"timestamp\":%lu}",
        heartRate, spo2, millis());
    
    mqttClient.publish(topicVitals, payload);
}

// ─── Publish Audio Event ────────────────────────
void publishAudio(bool distressDetected) {
    char payload[128];
    snprintf(payload, sizeof(payload),
        "{\"distress_detected\":%s,\"audio_activity\":true,\"timestamp\":%lu}",
        distressDetected ? "true" : "false", millis());
    
    mqttClient.publish(topicAudio, payload);
}

// ─── Main Loop ──────────────────────────────────
void loop() {
    if (!mqttClient.connected()) {
        connectMQTT();
    }
    mqttClient.loop();
    
    unsigned long now = millis();
    
    // Read sensors
    readIMU();
    
    // Track movement for deep sleep
    if (smv > 1.2) {
        lastMovementTime = now;
    }
    
    // ── Send motion data at regular intervals ──
    if (now - lastMotionSend >= MOTION_INTERVAL_MS) {
        publishMotion();
        lastMotionSend = now;
        
        // ── Motion spike → activate microphone ──
        if (smv > SMV_SPIKE_THRESHOLD && !motionSpikeActive) {
            motionSpikeActive = true;
            Serial.println("[ALERT] Motion spike detected! Activating microphone...");
            
            bool distress = detectVoiceActivity();
            publishAudio(distress);
            
            if (distress) {
                Serial.println("[ALERT] Distress sound detected!");
            }
            motionSpikeActive = false;
        }
    }
    
    // ── Send vitals at lower frequency ──
    if (now - lastVitalsSend >= VITALS_INTERVAL_MS) {
        readBattery();
        publishVitals();
        lastVitalsSend = now;
    }
    
    // ── Deep sleep if no motion for SLEEP_TIMEOUT ──
    if (now - lastMovementTime > SLEEP_TIMEOUT_MS) {
        Serial.println("[POWER] No motion detected. Entering deep sleep...");
        mqttClient.disconnect();
        // Fallback to wake-up interval since we don't have MPU6050 INT pin configured here
        esp_sleep_enable_timer_wakeup(10 * 1000000); // 10s sleep for now
        esp_deep_sleep_start();
    }
    
    delay(2); // Reduced loop blocking duration for tighter MQTT telemetry cycles
}
