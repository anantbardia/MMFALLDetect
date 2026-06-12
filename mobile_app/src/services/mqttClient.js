import Paho from 'paho-mqtt';
import AsyncStorage from '@react-native-async-storage/async-storage';

class MQTTService {
  constructor() {
    this.client = null;
    this.callbacks = {};
    this.isConnected = false;
    this.isConnecting = false;
    this.reconnectTimeout = null;
  }

  generateClientId() {
    return 'MMFALL_App_' + Math.random().toString(16).substring(2, 8);
  }

  async connect() {
    if (this.isConnected || this.isConnecting) {
      console.log('Already connected or connecting to MQTT broker');
      return;
    }
    this.isConnecting = true;

    return new Promise((resolve, reject) => {
      const clientId = this.generateClientId();
      const brokerUrl = "c52ac5aafe364324856f4bf4eaed8b2d.s1.eu.hivemq.cloud";
      const port = 8884; // HiveMQ uses 8884 for WebSockets WSS
      const username = "hivemq.webclient.1781292820732";
      const password = "pn:9fS$Q3v6A1BVb>O@r";
      
      this.client = new Paho.Client(brokerUrl, port, "/mqtt", clientId);

      this.client.onConnectionLost = (responseObject) => {
        this.isConnected = false;
        this.isConnecting = false;
        console.log('MQTT Connection Lost:', responseObject.errorMessage);
        if (this.callbacks['onConnectionLost']) {
          this.callbacks['onConnectionLost'](responseObject);
        }
        
        // Auto-reconnect after 3 seconds
        if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = setTimeout(() => {
          console.log('Attempting to auto-reconnect MQTT...');
          this.connect().then(() => {
            // Re-subscribe to topics after reconnect
            if (this.callbacks['onReconnect']) {
              this.callbacks['onReconnect']();
            }
          }).catch(e => console.log('Auto-reconnect failed', e));
        }, 3000);
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
        keepAliveInterval: 60,
        reconnect: true,
        onSuccess: () => {
          this.isConnected = true;
          this.isConnecting = false;
          console.log('MQTT Connected Successfully to HiveMQ!');
          resolve();
        },
        onFailure: (message) => {
          this.isConnected = false;
          this.isConnecting = false;
          console.error('MQTT Connection failed:', message.errorMessage);
          
          // Auto-reconnect on initial failure too
          if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
          this.reconnectTimeout = setTimeout(() => {
            console.log('Retrying MQTT connection...');
            this.connect();
          }, 5000);
          
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
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    if (this.client && this.isConnected) {
      this.client.disconnect();
      this.isConnected = false;
      this.isConnecting = false;
      console.log('MQTT Disconnected');
    }
  }

  on(event, callback) {
    this.callbacks[event] = callback;
  }
}

const mqttService = new MQTTService();
export default mqttService;
