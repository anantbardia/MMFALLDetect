import Paho from 'paho-mqtt';
import AsyncStorage from '@react-native-async-storage/async-storage';

class MQTTService {
  constructor() {
    this.client = null;
    this.callbacks = {};
    this.isConnected = false;
  }

  generateClientId() {
    return 'MMFALL_App_' + Math.random().toString(16).substring(2, 8);
  }

  async connect() {
    if (this.client && this.isConnected) {
      console.log('Already connected to MQTT broker');
      return;
    }

    return new Promise((resolve, reject) => {
      const clientId = this.generateClientId();
      const brokerUrl = "c52ac5aafe364324856f4bf4eaed8b2d.s1.eu.hivemq.cloud";
      const port = 8884; // HiveMQ uses 8884 for WebSockets WSS
      const username = "hivemq.webclient.1781292820732";
      const password = "pn:9fS$Q3v6A1BVb>O@r";
      
      this.client = new Paho.Client(brokerUrl, port, "/mqtt", clientId);

      this.client.onConnectionLost = (responseObject) => {
        this.isConnected = false;
        console.log('MQTT Connection Lost:', responseObject.errorMessage);
        if (this.callbacks['onConnectionLost']) {
          this.callbacks['onConnectionLost'](responseObject);
        }
      };

      this.client.onMessageArrived = (message) => {
        if (this.callbacks['onMessageArrived']) {
          this.callbacks['onMessageArrived'](message.destinationName, message.payloadString);
        }
      };

      const options = {
        timeout: 3,
        useSSL: true,
        userName: username,
        password: password,
        onSuccess: () => {
          this.isConnected = true;
          console.log('MQTT Connected Successfully to HiveMQ!');
          resolve();
        },
        onFailure: (message) => {
          this.isConnected = false;
          console.error('MQTT Connection failed:', message.errorMessage);
          reject(message);
        }
      };

      this.client.connect(options);
    });
  }

  subscribe(topic) {
    if (this.client && this.isConnected) {
      this.client.subscribe(topic);
      console.log(`Subscribed to topic: ${topic}`);
    } else {
      console.warn('Cannot subscribe, MQTT client not connected');
    }
  }

  publish(topic, payload) {
    if (this.client && this.isConnected) {
      const message = new Paho.Message(payload);
      message.destinationName = topic;
      this.client.send(message);
    } else {
      console.warn('Cannot publish, MQTT client not connected');
    }
  }

  disconnect() {
    if (this.client && this.isConnected) {
      this.client.disconnect();
      this.isConnected = false;
      console.log('MQTT Disconnected');
    }
  }

  on(event, callback) {
    this.callbacks[event] = callback;
  }
}

const mqttService = new MQTTService();
export default mqttService;
