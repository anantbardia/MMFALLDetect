import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, FlatList } from 'react-native';
import { useTheme } from '@react-navigation/native';
import mqttClient from '../services/mqttClient';

export default function EventsScreen() {
  const { colors } = useTheme();
  const [events, setEvents] = useState([
    { id: '1', title: 'System Initialized', timestamp: new Date().toISOString(), type: 'info' }
  ]);

  useEffect(() => {
    // Listen for new events from MQTT
    mqttClient.on('onMessageArrived', (topic, payload) => {
      if (topic === 'fall_detection/events') {
        const newEvent = {
          id: Date.now().toString(),
          title: 'Fall Detected',
          timestamp: new Date().toISOString(),
          type: 'alert'
        };
        setEvents(prev => [newEvent, ...prev]);
      }
    });
  }, []);

  const styles = StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: colors.background,
      padding: 16,
    },
    header: {
      fontSize: 28,
      fontWeight: 'bold',
      color: colors.text,
      marginBottom: 16,
    },
    eventCard: {
      backgroundColor: colors.surface,
      padding: 16,
      borderRadius: 16,
      marginBottom: 12,
      borderLeftWidth: 4,
      elevation: 1,
      shadowColor: colors.cardShadow,
      shadowOffset: { width: 0, height: 1 },
      shadowOpacity: 0.1,
      shadowRadius: 4,
    },
    eventTitle: {
      fontSize: 16,
      fontWeight: 'bold',
      color: colors.text,
      marginBottom: 4,
    },
    eventTime: {
      fontSize: 12,
      color: colors.textSecondary,
    }
  });

  const renderItem = ({ item }) => (
    <View style={[styles.eventCard, { borderLeftColor: item.type === 'alert' ? colors.danger : colors.primary }]}>
      <Text style={styles.eventTitle}>{item.title}</Text>
      <Text style={styles.eventTime}>{new Date(item.timestamp).toLocaleString()}</Text>
    </View>
  );

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Event History</Text>
      <FlatList
        data={events}
        keyExtractor={item => item.id}
        renderItem={renderItem}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingBottom: 40 }}
      />
    </View>
  );
}
