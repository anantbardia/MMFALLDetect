import React, { useEffect, useState, useRef } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, TextInput } from 'react-native';
import { useTheme } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import notificationService from '../services/notificationService';
import CameraFeed from '../components/CameraFeed';
import mqttClient from '../services/mqttClient';
import decisionEngine from '../services/decisionEngine';

export default function DashboardScreen() {
  const { colors } = useTheme();
  
  const [baseUrl, setBaseUrl] = useState('https://mmfalldetect.onrender.com');
  const [cameraUrl, setCameraUrl] = useState('https://spiritual-depletion-squint.ngrok-free.dev');
  
  const [isEditingUrl, setIsEditingUrl] = useState(false);
  const [tempBaseUrl, setTempBaseUrl] = useState(baseUrl);
  const [tempCameraUrl, setTempCameraUrl] = useState(cameraUrl);

  // System States
  const [wsConnected, setWsConnected] = useState(false);
  const [mqttConnected, setMqttConnected] = useState(false);
  const [mqttError, setMqttError] = useState('');
  const [systemState, setSystemState] = useState('NORMAL');
  const [isPersonVisible, setIsPersonVisible] = useState(false);
  const [vitals, setVitals] = useState({ hr: 0, spo2: 0 });
  const [hasVitals, setHasVitals] = useState(false);
  const [isAudioDistress, setIsAudioDistress] = useState(false);
  const [fallScore, setFallScore] = useState(0);
  const [devices, setDevices] = useState([]);
  const [motion, setMotion] = useState({ ax: 0, ay: 0, az: 0, smv: 0 });

  const wsRef = useRef(null);
  const cvTimeoutRef = useRef(null);
  const iotTimeoutRef = useRef(null);

  const [cvLive, setCvLive] = useState(false);
  const [iotLive, setIotLive] = useState(false);

  // Initialize WebSocket connection
  useEffect(() => {
    let isMounted = true;
    const wsUrl = baseUrl.replace(/^http/, 'ws');
    
    const connectWS = () => {
      console.log('Connecting to WS:', `${wsUrl}/ws/live-feed/patient_01`);
      const ws = new WebSocket(`${wsUrl}/ws/live-feed/patient_01`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isMounted) setWsConnected(true);
      };

      ws.onclose = () => {
        if (isMounted) {
          setWsConnected(false);
          // Auto-reconnect
          setTimeout(connectWS, 3000);
        }
      };

      ws.onerror = (e) => {
        console.log('WebSocket error:', e.message);
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const msg = JSON.parse(event.data);
          
          if (msg.fall_score !== undefined) setFallScore(msg.fall_score);

          // Route all CV-related backend messages to the Decision Engine
          if (msg.type === 'cv_update' || msg.fall_score !== undefined || msg.system_state) {
            setCvLive(true);
            if (cvTimeoutRef.current) clearTimeout(cvTimeoutRef.current);
            cvTimeoutRef.current = setTimeout(() => setCvLive(false), 5000);

            if (msg.type === 'cv_update') {
              setIsPersonVisible(msg.data?.person_visible ?? false);
            }
            decisionEngine.updateCVData(msg);
          }

          // Read Vitals from WebSocket heartbeat/iot_update as a fallback to direct MQTT
          if (msg.type === 'heartbeat') {
            if (msg.vitals && (msg.vitals.heart_rate !== 75 || msg.vitals.spo2 !== 98)) {
              setHasVitals(true);
              setVitals({ hr: msg.vitals.heart_rate, spo2: msg.vitals.spo2 });
            }
          }
          if (msg.type === 'iot_update' && msg.data) {
            if (msg.data.heart_rate || msg.data.spo2) {
              setHasVitals(true);
              setVitals(v => ({ hr: msg.data.heart_rate ?? v.hr, spo2: msg.data.spo2 ?? v.spo2 }));
            }
          }
          
          // Fallback to backend system_state only if decision engine isn't overriding
          if (msg.system_state && decisionEngine.currentState === 'NORMAL') {
            setSystemState(prev => {
              if (prev === 'FALL_CONFIRMED' && msg.system_state !== 'FALL_CONFIRMED') {
                return prev; // Latch until manually acknowledged!
              }
              return msg.system_state;
            });
          }
        } catch (e) {
          console.log('Parse error:', e);
        }
      };
    };

    connectWS();

    return () => {
      isMounted = false;
      if (wsRef.current) wsRef.current.close();
    };
  }, [baseUrl]);

  // Fetch Device Health
  useEffect(() => {
    let interval;
    const fetchDevices = async () => {
      try {
        const res = await fetch(`${baseUrl}/api/v1/devices`);
        const data = await res.json();
        setDevices(data.devices || []);
      } catch (e) {
        // backend offline
      }
    };
    fetchDevices();
    interval = setInterval(fetchDevices, 10000);
    return () => clearInterval(interval);
  }, [baseUrl]);

  // Trigger Local Notification on Fall
  useEffect(() => {
    if (['POSSIBLE_FALL', 'FALL_CONFIRMED'].includes(systemState)) {
      notificationService.sendLocalNotification(
        '⚠️ FALL DETECTED!', 
        `Critical alert: System state is currently ${systemState.replace('_', ' ')}`
      );
    }
  }, [systemState]);

  // Direct MQTT Setup for True Edge Computing
  useEffect(() => {
    let isMounted = true;
    
    // Listen for Decision Engine overrides
    decisionEngine.onStateChange = (newState) => {
      if (isMounted) setSystemState(newState);
    };

    const setupMQTT = async () => {
      try {
        await mqttClient.connect();
        if (isMounted) {
          setMqttConnected(true);
          setMqttError('');
        }
        
        mqttClient.subscribe('fall_detection/motion/patient_01');
        mqttClient.subscribe('fall_detection/vitals/patient_01');
        mqttClient.subscribe('fall_detection/audio/patient_01');
        
        mqttClient.on('onConnectionLost', (err) => {
          if (isMounted) {
            setMqttConnected(false);
            setMqttError('Connection Lost (Reconnecting...)');
          }
        });

        mqttClient.on('onReconnect', () => {
          if (isMounted) {
            setMqttConnected(true);
            setMqttError('');
            mqttClient.subscribe('fall_detection/motion/patient_01');
            mqttClient.subscribe('fall_detection/vitals/patient_01');
            mqttClient.subscribe('fall_detection/audio/patient_01');
          }
        });

        mqttClient.on('onMessageArrived', (topic, payload) => {
          if (!isMounted) return;
          try {
            if (topic.includes('motion') || topic.includes('vitals') || topic.includes('audio')) {
              setIotLive(true);
              if (iotTimeoutRef.current) clearTimeout(iotTimeoutRef.current);
              iotTimeoutRef.current = setTimeout(() => setIotLive(false), 5000);
            }

            const data = JSON.parse(payload);
            if (topic.includes('motion')) {
              setMotion({ ax: data.ax, ay: data.ay, az: data.az, smv: data.smv });
              decisionEngine.updateIoTData(data); // Feed to AI Decision Engine
            } else if (topic.includes('vitals')) {
              setHasVitals(true);
              setVitals({ hr: data.heart_rate, spo2: data.spo2 });
            } else if (topic.includes('audio')) {
              setIsAudioDistress(data.distress_detected === true || data.distress_detected === "true");
            }
          } catch (e) {
            console.log('MQTT Parse error:', e);
          }
        });
      } catch (e) {
        console.log('MQTT Connect Error:', e);
        if (isMounted) {
          setMqttConnected(false);
          setMqttError(e.errorMessage || 'Failed to connect');
        }
      }
    };
    
    setupMQTT();
    
    return () => {
      isMounted = false;
      mqttClient.disconnect();
    };
  }, []);

  const handleSaveUrl = () => {
    setBaseUrl(tempBaseUrl);
    setCameraUrl(tempCameraUrl);
    setIsEditingUrl(false);
  };

  const acknowledgeAlert = async () => {
    decisionEngine.acknowledge();
    setSystemState('NORMAL');
    try {
      await fetch(`${baseUrl}/api/v1/alerts/patient_01/acknowledge`, { method: 'POST' });
    } catch (e) {
      console.log('Ack failed:', e);
    }
  };

  const isEmergency = ['POSSIBLE_FALL', 'FALL_CONFIRMED', 'MEDICAL_ALERT', 'ALERT_SENT'].includes(systemState);

  const getStatusColor = () => {
    switch (systemState) {
      case 'NORMAL': return colors.success;
      case 'POSSIBLE_FALL': return '#fbbf24'; // amber
      case 'FALL_CONFIRMED': return '#f97316'; // orange
      case 'MEDICAL_ALERT':
      case 'ALERT_SENT': return colors.danger; // red
      case 'RECOVERY': return colors.primary; // blue
      default: return colors.textSecondary;
    }
  };

  const styles = StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background, padding: 16 },
    header: { fontSize: 26, fontWeight: 'bold', color: colors.text, marginBottom: 4 },
    subtitle: { fontSize: 13, color: colors.textSecondary, marginBottom: 16 },
    
    statusCard: {
      flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
      backgroundColor: colors.surface, padding: 12, borderRadius: 12,
      borderWidth: 1, borderColor: colors.border, marginBottom: 16
    },
    badge: {
      paddingHorizontal: 12, paddingVertical: 4, borderRadius: 8,
      borderWidth: 1
    },
    badgeText: { fontWeight: 'bold', fontSize: 12 },

    configContainer: {
      backgroundColor: colors.surface, borderRadius: 12, padding: 12,
      borderWidth: 1, borderColor: colors.border, marginBottom: 20
    },
    urlInput: {
      backgroundColor: colors.background, borderColor: colors.border, borderWidth: 1,
      borderRadius: 8, padding: 10, color: colors.text, marginBottom: 8
    },
    urlButton: { backgroundColor: colors.primary, borderRadius: 8, padding: 10, alignItems: 'center' },
    
    emergencyBanner: {
      backgroundColor: colors.danger + '10', borderColor: colors.danger, borderWidth: 2,
      borderRadius: 16, padding: 16, marginBottom: 20, alignItems: 'center'
    },
    ackButton: {
      backgroundColor: colors.danger, paddingHorizontal: 20, paddingVertical: 10,
      borderRadius: 8, marginTop: 12
    },
    
    sectionTitle: { fontSize: 18, fontWeight: 'bold', color: colors.text, marginBottom: 12, marginTop: 8 },
    
    grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', marginBottom: 20 },
    card: {
      backgroundColor: colors.surface, width: '48%', padding: 14, borderRadius: 12,
      borderWidth: 1, borderColor: colors.border, marginBottom: 16
    },
    cardTitle: { fontSize: 12, color: colors.textSecondary, fontWeight: 'bold', marginBottom: 6 },
    cardValue: { fontSize: 22, fontWeight: 'bold', color: colors.text },
    
    deviceRow: {
      flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
      paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border
    }
  });

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      <Text style={styles.header}>Fall-o-Up Monitor</Text>
      <Text style={styles.subtitle}>Intelligent Fall Detection System</Text>
      
      {/* WS Status & System State */}
      <View style={styles.statusCard}>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <View style={[styles.badge, { backgroundColor: (wsConnected && cvLive) ? colors.success + '20' : colors.danger + '20', borderColor: (wsConnected && cvLive) ? colors.success : colors.danger }]}>
            <Text style={[styles.badgeText, { color: (wsConnected && cvLive) ? colors.success : colors.danger }]}>
              CV: {(wsConnected && cvLive) ? 'LIVE' : 'OFFLINE'}
            </Text>
          </View>
          <View style={[styles.badge, { backgroundColor: (mqttConnected && iotLive) ? colors.success + '20' : colors.danger + '20', borderColor: (mqttConnected && iotLive) ? colors.success : colors.danger }]}>
            <Text style={[styles.badgeText, { color: (mqttConnected && iotLive) ? colors.success : colors.danger }]}>
              IOT: {(mqttConnected && iotLive) ? 'LIVE' : mqttError || 'OFFLINE'}
            </Text>
          </View>
        </View>
        <View style={[styles.badge, { backgroundColor: getStatusColor() + '20', borderColor: getStatusColor() }]}>
          <Text style={[styles.badgeText, { color: getStatusColor() }]}>{systemState.replace('_', ' ')}</Text>
        </View>
      </View>

      {/* URL Configs */}
      <View style={styles.configContainer}>
        {isEditingUrl ? (
          <View>
            <Text style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }}>Backend API URL (WebSockets)</Text>
            <TextInput style={styles.urlInput} value={tempBaseUrl} onChangeText={setTempBaseUrl} placeholder="e.g. https://mmfalldetect.onrender.com" />
            
            <Text style={{ fontSize: 11, color: colors.textSecondary, marginBottom: 4 }}>Camera Feed URL (Ngrok)</Text>
            <TextInput style={styles.urlInput} value={tempCameraUrl} onChangeText={setTempCameraUrl} placeholder="e.g. https://xxxx.ngrok-free.dev" />
            
            <TouchableOpacity style={styles.urlButton} onPress={handleSaveUrl}>
              <Text style={{ color: 'white', fontWeight: 'bold' }}>Save Configurations</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity onPress={() => setIsEditingUrl(true)} style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
            <View style={{ flex: 1 }}>
              <Text style={{ fontSize: 11, color: colors.textSecondary }}>Backend API URL</Text>
              <Text style={{ fontSize: 13, color: colors.text, marginTop: 2, marginBottom: 8 }} numberOfLines={1}>{baseUrl}</Text>
              
              <Text style={{ fontSize: 11, color: colors.textSecondary }}>Camera Feed URL</Text>
              <Text style={{ fontSize: 13, color: colors.text, marginTop: 2 }} numberOfLines={1}>{cameraUrl}</Text>
            </View>
            <Text style={{ color: colors.primary, fontWeight: 'bold', marginLeft: 10 }}>Edit</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Emergency Banner */}
      {isEmergency && (
        <View style={styles.emergencyBanner}>
          <Ionicons name="warning" size={40} color={colors.danger} />
          <Text style={{ fontSize: 18, fontWeight: 'bold', color: colors.danger, marginTop: 8 }}>CRITICAL: FALL DETECTED!</Text>
          <Text style={{ color: colors.text, textAlign: 'center', marginTop: 4 }}>
            Camera Confidence: {(fallScore * 100).toFixed(0)}%.
            Vitals: {hasVitals ? `HR ${vitals.hr} | SpO₂ ${vitals.spo2}%` : 'Standby'}
          </Text>
          <TouchableOpacity style={styles.ackButton} onPress={acknowledgeAlert}>
            <Text style={{ color: 'white', fontWeight: 'bold' }}>Acknowledge & Clear Alarm</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Live Camera Feed */}
      <Text style={styles.sectionTitle}>Camera Feed</Text>
      <View style={{ marginBottom: 16 }}>
        <CameraFeed streamUrl={`${cameraUrl}/video_feed`} title="Primary Camera Node" />
      </View>

      {/* Vitals Grid */}
      <Text style={styles.sectionTitle}>Live Vitals & Sensors</Text>
      <View style={styles.grid}>
        <View style={styles.card}>
          <Text style={[styles.cardTitle, { color: colors.danger }]}>
            <Ionicons name="heart" size={12} /> Heart Rate
          </Text>
          <Text style={styles.cardValue}>{hasVitals ? `${vitals.hr} BPM` : '--'}</Text>
        </View>
        <View style={styles.card}>
          <Text style={[styles.cardTitle, { color: '#0ea5e9' }]}>
            <Ionicons name="water" size={12} /> Blood Oxygen
          </Text>
          <Text style={styles.cardValue}>{hasVitals ? `${vitals.spo2}%` : '--'}</Text>
        </View>
        <View style={styles.card}>
          <Text style={[styles.cardTitle, { color: '#8b5cf6' }]}>
            <Ionicons name="pulse" size={12} /> Motion (SMV)
          </Text>
          <Text style={styles.cardValue}>{motion.smv.toFixed(2)} g</Text>
        </View>
        <View style={styles.card}>
          <Text style={[styles.cardTitle, { color: isAudioDistress ? '#f59e0b' : colors.textSecondary }]}>
            <Ionicons name="mic" size={12} /> Audio Distress
          </Text>
          <Text style={[styles.cardValue, { fontSize: 16, color: isAudioDistress ? '#f59e0b' : colors.success }]}>
            {isAudioDistress ? 'DETECTED' : 'QUIET'}
          </Text>
        </View>
      </View>

      {/* Device Health */}
      <Text style={styles.sectionTitle}>Device Health</Text>
      <View style={[styles.configContainer, { padding: 16 }]}>
        {devices.length > 0 ? devices.map((d, i) => (
          <View key={i} style={styles.deviceRow}>
            <View>
              <Text style={{ color: colors.text, fontWeight: 'bold', fontSize: 13 }}>{d.mac_address}</Text>
              <Text style={{ color: colors.textSecondary, fontSize: 11 }}>{d.device_type}</Text>
            </View>
            <View style={{ alignItems: 'flex-end' }}>
              {d.battery_level && <Text style={{ color: colors.textSecondary, fontSize: 11 }}>Bat: {d.battery_level}%</Text>}
              <Text style={{ color: d.status === 'ONLINE' ? colors.success : colors.textSecondary, fontSize: 11, fontWeight: 'bold' }}>
                {d.status}
              </Text>
            </View>
          </View>
        )) : (
          <Text style={{ color: colors.textSecondary, textAlign: 'center' }}>No devices found</Text>
        )}
      </View>
      
      <View style={{ height: 40 }} />
    </ScrollView>
  );
}
