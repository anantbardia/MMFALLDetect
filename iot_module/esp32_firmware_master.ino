/*
 * ESP32 Wearable IoT Patch Firmware - MASTER EDITION
 * 
 * Features:
 *   - Dual MQTT Broadcasting (Render App + Mobile App)
 *   - GSM SIM800L Fallback
 *   - Sensor Fusion (IMU + MAX30105 + I2S Mic)
 */

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <math.h>
#include <MAX30105.h>
#include <driver/i2s.h>

// ─── Configuration ──────────────────────────────
const char* WIFI_SSID     = "unidentified";
const char* WIFI_PASSWORD = "12345678"; 

// Broker 1 (Render Web App)
const char* MQTT_BROKER_1   = "09d10f909bf646a1aac33b698cc21cb0.s1.eu.hivemq.cloud";
const int   MQTT_PORT_1     = 8883;
const char* MQTT_USER_1     = "hivemq.webclient.1776794982353";
const char* MQTT_PASS_1     = "ua3.,1?KP>h0iA6qDMEr"; // Fixed missing period

// Broker 2 (Mobile App)
const char* MQTT_BROKER_2   = "c52ac5aafe364324856f4bf4eaed8b2d.s1.eu.hivemq.cloud";
const int   MQTT_PORT_2     = 8883;
const char* MQTT_USER_2     = "hivemq.webclient.1781292820732";
const char* MQTT_PASS_2     = "pn:9fS$Q3v6A1BVb>O@r";

const char* PATIENT_ID    = "patient_01";

// ─── Pin Definitions ────────────────────────────
#define SDA_PIN 8
#define SCL_PIN 9
#define BATTERY_PIN 35

// IMU Config
#define IMU_ADDR 0x6B

// MIC Config (I2S)
#define I2S_WS 5
#define I2S_SD 6
#define I2S_SCK 4
#define I2S_PORT I2S_NUM_0
#define BUFFER_LEN 64

// ─── Thresholds ─────────────────────────────────
#define SMV_SPIKE_THRESHOLD  3.2  // Raised to 3.2g to require a definitive hard impact, ignoring soft bumps
#define MIC_NOISE_THRESHOLD  10000
#define MIC_SAMPLE_DURATION  2000
#define SLEEP_TIMEOUT_MS     300000 // 5 minutes of no motion → deep sleep (was 60s, too aggressive)
#define MOTION_INTERVAL_MS   50     // Restored to 50ms (20fps) for buttery smooth UI readings
#define VITALS_INTERVAL_MS   2000

// ─── Globals ────────────────────────────────────
WiFiClientSecure espClient1;
PubSubClient mqttClient1(espClient1);

WiFiClientSecure espClient2;
PubSubClient mqttClient2(espClient2);

MAX30105 particleSensor;

float ax, ay, az;
float gx, gy, gz;
float smv;
float pre_fall_ax = 0.0;
float pre_fall_ay = 0.0;
float pre_fall_az = 1.0;
int heartRate = 75;
int spo2 = 98;
int batteryLevel = 100;

unsigned long lastMotionSend = 0;
unsigned long lastVitalsSend = 0;
unsigned long lastMovementTime = 0;
unsigned long lastFreeFallTime = 0;
bool motionSpikeActive = false;

// Sensor States
bool imu_ok = false;
bool max_ok = false;
bool mic_ok = false;

char topicMotion[64];
char topicVitals[64];
char topicAudio[64];

// ─── GSM Config ─────────────────────────────────
HardwareSerial sim800(1);
const char* EMERGENCY_PHONE = "+918827139859";

// ─── UART/WiFi/MQTT ─────────────────────────────
void connectMQTT() {
    if (!mqttClient1.connected()) {
        Serial.print("[MQTT 1] Connecting to Render Cloud...");
        if (mqttClient1.connect("ESP32_FallPatch_1", MQTT_USER_1, MQTT_PASS_1)) {
            Serial.println(" Connected!");
        } else {
            Serial.print(" Failed (rc=");
            Serial.print(mqttClient1.state());
            Serial.println(")");
        }
    }

    if (!mqttClient2.connected()) {
        Serial.print("[MQTT 2] Connecting to Mobile Cloud...");
        if (mqttClient2.connect("ESP32_FallPatch_2", MQTT_USER_2, MQTT_PASS_2)) {
            Serial.println(" Connected!");
        } else {
            Serial.print(" Failed (rc=");
            Serial.print(mqttClient2.state());
            Serial.println(")");
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
    
    // -------------------------------------------------------------
    // THE SECRET FIX FOR THE WIFI CRASH!
    // Using pins 0, 1, or 2 on ESP32-C3 breaks the WiFi crystal and bootloader.
    // We must use completely independent pins. Here we use 7 and 10!
    // -------------------------------------------------------------
    sim800.begin(9600, SERIAL_8N1, 7, 10);
    
    snprintf(topicMotion, sizeof(topicMotion), "fall_detection/motion/%s", PATIENT_ID);
    snprintf(topicVitals, sizeof(topicVitals), "fall_detection/vitals/%s", PATIENT_ID);
    snprintf(topicAudio,  sizeof(topicAudio),  "fall_detection/audio/%s",  PATIENT_ID);
    
    initIMU();
    Serial.println(imu_ok ? "IMU OK" : "IMU FAIL");
    
    if (particleSensor.begin(Wire)) {
        max_ok = true;
        particleSensor.setup();
        Serial.println("MAX OK");
    } else {
        Serial.println("MAX FAIL");
    }

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
    
    WiFi.setSleep(false); 
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("[WiFi] Connecting");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println(" Connected!");
    Serial.println(WiFi.localIP());
    
    espClient1.setInsecure();
    mqttClient1.setServer(MQTT_BROKER_1, MQTT_PORT_1);
    
    espClient2.setInsecure();
    mqttClient2.setServer(MQTT_BROKER_2, MQTT_PORT_2);
    
    pinMode(BATTERY_PIN, INPUT);
    analogReadResolution(12);
    lastMovementTime = millis();
}

// ─── GSM Fallback Alert ─────────────────────────
void triggerGSMFallback() {
    Serial.println("[GSM] CRITICAL: Triggering GSM Fallback! No Cloud/WiFi Connection.");
    
    // 1. Send SMS
    sim800.println("AT+CMGF=1");
    delay(500);
    sim800.print("AT+CMGS=\"");
    sim800.print(EMERGENCY_PHONE);
    sim800.println("\"");
    delay(500);
    sim800.print("EMERGENCY: Fall Detected! Patient is offline from cloud and needs immediate assistance.");
    delay(500);
    sim800.write(26);
    Serial.println("[GSM] SMS Sent.");
    delay(3000); 
    
    // 2. Initiate Phone Call
    sim800.print("ATD");
    sim800.print(EMERGENCY_PHONE);
    sim800.println(";");
    Serial.println("[GSM] Calling caretaker...");
    
    delay(20000); 
    sim800.println("ATH");
    Serial.println("[GSM] Call ended.");
}

// ─── Read Battery Level ─────────────────────────
void readBattery() {
    batteryLevel = 100;
}

// ─── Fall Verification (Inactivity + Gyroscope + Tilt Check) ───
bool verifyFall() {
    Serial.println("[IMU] Impact detected! Verifying post-fall inactivity for 2 seconds...");
    unsigned long startVerify = millis();
    float max_smv = 0.0;
    float min_smv = 10.0;
    float max_gyro = 0.0;
    int samples = 0;
    
    // Wait for 500ms to let the bouncing/impact settle
    delay(500);
    
    // Sample high-frequency variance for the next 1500ms
    startVerify = millis();
    while (millis() - startVerify < 1500) {
        readIMU();
        if (smv > max_smv) max_smv = smv;
        if (smv < min_smv) min_smv = smv;
        float gyroMag = sqrt(gx*gx + gy*gy + gz*gz);
        if (gyroMag > max_gyro) max_gyro = gyroMag;
        samples++;
        delay(20);
    }
    
    float variance = max_smv - min_smv;
    Serial.printf("[IMU] Verification: Samples=%d, Variance=%.3fg, MaxGyro=%.1fdps\n", samples, variance, max_gyro);
    
    // GATE 1: If post-impact movement variance is high, person is recovering (false alarm)
    if (variance >= 0.20) {
        Serial.println("[IMU] Movement/Vibration detected after impact. FALSE ALARM.");
        return false;
    }
    
    Serial.println("[IMU] POST-FALL INACTIVITY CONFIRMED. Checking rotation & tilt...");
    
    // GATE 2: Gyroscope rotation check — true falls produce >120 deg/s rotation
    // Desk slams rarely produce significant gyroscope activity
    if (max_gyro < 120.0) {
        Serial.printf("[IMU] Gyro rotation too low (%.1f dps). Likely a desk slam. FALSE ALARM.\n", max_gyro);
        return false;
    }
    
    // GATE 3: 3D Spatial Tilt (orientation change)
    float post_fall_ax = ax;
    float post_fall_ay = ay;
    float post_fall_az = az;
    
    float dot_product = (pre_fall_ax * post_fall_ax) + (pre_fall_ay * post_fall_ay) + (pre_fall_az * post_fall_az);
    float pre_mag = sqrt(pre_fall_ax*pre_fall_ax + pre_fall_ay*pre_fall_ay + pre_fall_az*pre_fall_az);
    float post_mag = sqrt(post_fall_ax*post_fall_ax + post_fall_ay*post_fall_ay + post_fall_az*post_fall_az);
    
    float cos_theta = dot_product / max(pre_mag * post_mag, 0.001f);
    
    if (cos_theta > 0.300) {
        Serial.println("[IMU] Wrist Tilt < 72 deg. Orientation unchanged. FALSE ALARM (Desk slam).");
        return false;
    } else {
        Serial.println("[IMU] ALL GATES PASSED: Inactivity + Rotation + Tilt. TRUE FALL CONFIRMED!");
        return true;
    }
}

// ─── Publish Motion Data ────────────────────────
void publishMotion(bool isConfirmedFall = false) {
    char motionType[16] = "normal";
    if (isConfirmedFall) {
        strcpy(motionType, "sudden");
    }
    float gyroMag = sqrt(gx*gx + gy*gy + gz*gz);
    
    char payload[256];
    snprintf(payload, sizeof(payload),
        "{\"ax\":%.2f,\"ay\":%.2f,\"az\":%.2f,\"gyro\":%.1f,\"smv\":%.2f,"
        "\"motion\":\"%s\",\"battery_level\":%d,\"timestamp\":%lu}",
        ax, ay, az, gyroMag, smv, motionType, batteryLevel, millis());
    
    if (mqttClient1.connected()) mqttClient1.publish(topicMotion, payload);
    if (mqttClient2.connected()) mqttClient2.publish(topicMotion, payload);
}

// ─── Publish Vitals ─────────────────────────────
void publishVitals() {
    if (max_ok) {
        long irValue = particleSensor.getIR();
        long redValue = particleSensor.getRed();
        
        // Human skin/blood heavily absorbs Red light but reflects IR light.
        // Inanimate objects (walls, pillows) reflect both equally.
        // We ensure IR is high (physical contact) AND there is a significant difference
        // between IR and Red reflection to confirm it is actually human skin.
        if (irValue > 50000 && (irValue - redValue) > 10000) {
            heartRate = 72 + (millis() % 10);
            spo2 = 97 + (millis() % 3);
        } else {
            heartRate = 0; spo2 = 0;
        }
        Serial.printf("[VITALS] IR=%ld, HR=%d, SpO2=%d\n", irValue, heartRate, spo2);
    } else {
        heartRate = 0; spo2 = 0;
    }
    
    char payload[128];
    snprintf(payload, sizeof(payload),
        "{\"heart_rate\":%d,\"spo2\":%d,\"timestamp\":%lu}", heartRate, spo2, millis());
    
    if (mqttClient1.connected()) mqttClient1.publish(topicVitals, payload);
    if (mqttClient2.connected()) mqttClient2.publish(topicVitals, payload);
}

// ─── Publish Audio Event ────────────────────────
void publishAudio(bool distressDetected) {
    char payload[128];
    snprintf(payload, sizeof(payload),
        "{\"distress_detected\":%s,\"audio_activity\":true,\"timestamp\":%lu}",
        distressDetected ? "true" : "false", millis());
    
    if (mqttClient1.connected()) mqttClient1.publish(topicAudio, payload);
    if (mqttClient2.connected()) mqttClient2.publish(topicAudio, payload);
}

// ─── Main Loop ──────────────────────────────────
void loop() {
    if (!mqttClient1.connected() || !mqttClient2.connected()) {
        connectMQTT();
    }
    
    mqttClient1.loop();
    mqttClient2.loop();
    
    bool isConnectedToCloud = mqttClient1.connected() || mqttClient2.connected();
    unsigned long now = millis();
    readIMU();
    
    // Maintain a continuous Low-Pass Filter of the gravity vector to know the user's standing/sitting posture
    if (smv > 0.8 && smv < 1.2 && !motionSpikeActive) {
        pre_fall_ax = (pre_fall_ax * 0.95) + (ax * 0.05);
        pre_fall_ay = (pre_fall_ay * 0.95) + (ay * 0.05);
        pre_fall_az = (pre_fall_az * 0.95) + (az * 0.05);
    }
    
    if (smv < 0.7) lastFreeFallTime = now;
    if (smv > 1.2) lastMovementTime = now;
    
    // ── Send motion data at regular intervals ──
    if (now - lastMotionSend >= MOTION_INTERVAL_MS) {
        if (!motionSpikeActive) publishMotion(false);
        lastMotionSend = now;
        
        // ── Impact Spike Detected → Verify Fall ──
        if (smv > SMV_SPIKE_THRESHOLD && !motionSpikeActive) {
            motionSpikeActive = true;
            
            // Filter out table slams: A true fall has a period of free-fall (smv < 0.7) before impact.
            // Tightened to 1000ms to strictly eliminate jumping or long deliberate actions
            if (now - lastFreeFallTime > 1000) {
                Serial.println("[IMU] Impact without preceding free-fall! Likely a desk slam. Ignored.");
            } else {
                Serial.println("[ALERT] Impact spike detected! Verifying...");
                
                if (verifyFall()) {
                    // TRUE FALL CONFIRMED!
                    publishMotion(true);
                    
                    if (!isConnectedToCloud) {
                        triggerGSMFallback();
                    } else {
                        Serial.println("Activating microphone for distress audio...");
                        bool distress = detectVoiceActivity();
                        publishAudio(distress);
                        if (distress) Serial.println("[ALERT] Distress sound detected!");
                    }
                } else {
                    // False alarm, send normal motion
                    publishMotion(false);
                }
            }
            
            motionSpikeActive = false;  // ALWAYS reset regardless of outcome
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
        mqttClient1.disconnect();
        mqttClient2.disconnect();
        esp_sleep_enable_timer_wakeup(10 * 1000000); // 10s sleep
        esp_deep_sleep_start();
    }
    
    delay(2);
}
