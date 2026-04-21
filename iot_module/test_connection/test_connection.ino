/*
 * ESP32 C3 Mini - Simple WiFi & MQTT Connection Test
 * 
 * This sketch does not require any physical sensors.
 * It connects to your WiFi, connects to your Mosquitto MQTT broker,
 * and publishes a simple "Hello from ESP32" message every 5 seconds.
 * It also subscribes to a topic so you can test sending messages TO the ESP32.
 */

#include <WiFi.h>
#include <PubSubClient.h>

// ─── YOUR SETTINGS HERE ──────────────────────────────
const char* WIFI_SSID     = "unidentified";           // Replace with your WiFi Name
const char* WIFI_PASSWORD = "12345678";       // Replace with your WiFi Password

// IMPORTANT: Replace this with the IPv4 address of your PC!
// Open cmd on Windows, type `ipconfig`, look for IPv4 Address (e.g., 192.168.1.XX)
const char* MQTT_BROKER   = "10.186.7.39";  
const int   MQTT_PORT     = 1883;

// Topics for testing
const char* PUBLISH_TOPIC   = "test/esp32/status";
const char* SUBSCRIBE_TOPIC = "test/esp32/commands";
// ───────────────────────────────────────────────────

WiFiClient espClient;
PubSubClient mqttClient(espClient);

unsigned long lastMsgTime = 0;
int msgCount = 0;

void setup() {
    // Start serial monitor (set baud rate to 115200 in Arduino IDE)
    Serial.begin(115200);
    delay(1000); // Give serial monitor time to open
    
    Serial.println("\n--- ESP32 C3 Mini MQTT Test Start ---");

    // 1. Connect to WiFi
    Serial.print("Connecting to WiFi network: ");
    Serial.println(WIFI_SSID);
    
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    
    Serial.println("\nWiFi connected successfully!");
    Serial.print("ESP32 IP Address: ");
    Serial.println(WiFi.localIP());
    
    // 2. Setup MQTT
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    mqttClient.setCallback(mqttCallback);
    
    connectMQTT();
}

void loop() {
    // Reconnect if MQTT connection drops
    if (!mqttClient.connected()) {
        connectMQTT();
    }
    mqttClient.loop(); // Required to keep MQTT connection alive
    
    // Publish a test message every 5 seconds
    unsigned long now = millis();
    if (now - lastMsgTime > 5000) {
        lastMsgTime = now;
        msgCount++;
        
        char payload[50];
        snprintf(payload, sizeof(payload), "Hello from ESP32! Message #%d", msgCount);
        
        Serial.print("Publishing message: ");
        Serial.println(payload);
        
        bool success = mqttClient.publish(PUBLISH_TOPIC, payload);
        if (success) {
            Serial.println("  -> Publish Successful");
        } else {
            Serial.println("  -> Publish Failed");
        }
    }
}

// ─── Make MQTT Connection ────────────────────────────
void connectMQTT() {
    while (!mqttClient.connected()) {
        Serial.print("Connecting to MQTT broker at ");
        Serial.print(MQTT_BROKER);
        Serial.print("...");
        
        // Connect with a random client ID
        String clientId = "ESP32C3-Test-" + String(random(0xffff), HEX);
        
        if (mqttClient.connect(clientId.c_str())) {
            Serial.println(" Connected!");
            
            // Subscribe to our incoming test topic
            mqttClient.subscribe(SUBSCRIBE_TOPIC);
            Serial.print("Subscribed to topic: ");
            Serial.println(SUBSCRIBE_TOPIC);
        } else {
            Serial.print(" Failed, MQTT State = ");
            Serial.print(mqttClient.state());
            Serial.println(". Retrying in 5 seconds...");
            delay(5000);
        }
    }
}

// ─── Callback for receiving messages ──────────────────
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    Serial.print("\n>>> Message arrived on topic: ");
    Serial.println(topic);
    
    Serial.print("<<< Message content: ");
    for (int i = 0; i < length; i++) {
        Serial.print((char)payload[i]);
    }
    Serial.println("\n");
}
