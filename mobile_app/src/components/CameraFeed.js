import React, { useState } from 'react';
import { View, StyleSheet, ActivityIndicator, Text, TouchableOpacity, Modal, SafeAreaView, Image } from 'react-native';
import { WebView } from 'react-native-webview';
import { useTheme } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';

export default function CameraFeed({ streamUrl, title }) {
  const { colors } = useTheme();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [isFullScreen, setIsFullScreen] = useState(false);

  const styles = StyleSheet.create({
    container: {
      width: '100%',
      height: 220,
      backgroundColor: colors.surface,
      borderRadius: 16,
      overflow: 'hidden',
      marginBottom: 16,
      borderWidth: 1,
      borderColor: colors.border,
      elevation: 2,
      shadowColor: colors.cardShadow,
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.1,
      shadowRadius: 8,
    },
    header: {
      paddingHorizontal: 16,
      paddingVertical: 10,
      borderBottomWidth: 1,
      borderBottomColor: colors.border,
      backgroundColor: colors.surface,
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
    },
    title: {
      fontSize: 14,
      fontWeight: 'bold',
      color: colors.text,
    },
    badge: {
      paddingHorizontal: 8,
      paddingVertical: 2,
      borderRadius: 8,
      backgroundColor: error ? colors.danger + '20' : colors.success + '20',
    },
    badgeText: {
      fontSize: 11,
      fontWeight: 'bold',
      color: error ? colors.danger : colors.success,
    },
    videoWrapper: {
      flex: 1,
      backgroundColor: '#000000',
      justifyContent: 'center',
      alignItems: 'center',
    },
    webview: {
      flex: 1,
      width: '100%',
      height: '100%',
      backgroundColor: '#000000',
    },
    loader: {
      position: 'absolute',
      alignSelf: 'center',
    },
    errorText: {
      color: colors.danger,
      fontSize: 14,
      fontWeight: '500',
    }
  });

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{title || 'Camera Stream'}</Text>
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{error ? 'Offline' : 'Live'}</Text>
        </View>
      </View>

      <View style={styles.videoWrapper}>
        {streamUrl && !error ? (
          <>
            <WebView
              style={styles.webview}
              source={{ html: `<html><body style="margin:0;padding:0;background-color:black;display:flex;justify-content:center;align-items:center;"><img src="${streamUrl}" style="width:100%;height:100%;object-fit:contain;" /></body></html>` }}
              scrollEnabled={false}
              showsHorizontalScrollIndicator={false}
              showsVerticalScrollIndicator={false}
              onLoadStart={() => setLoading(true)}
              onLoadEnd={() => setLoading(false)}
              onError={() => {
                setError(true);
                setLoading(false);
              }}
            />
            <TouchableOpacity 
              onPress={() => setIsFullScreen(true)} 
              style={{ position: 'absolute', bottom: 10, right: 10, backgroundColor: 'rgba(0,0,0,0.6)', padding: 8, borderRadius: 20, zIndex: 10, elevation: 5 }}
            >
              <Ionicons name="expand" size={20} color="white" />
            </TouchableOpacity>
          </>
        ) : (
          <Text style={styles.errorText}>No camera stream available</Text>
        )}

        {loading && !error && (
          <ActivityIndicator 
            color={colors.primary} 
            size="large" 
            style={styles.loader} 
          />
        )}
      </View>

      <Modal visible={isFullScreen} animationType="fade" transparent={false} onRequestClose={() => setIsFullScreen(false)}>
        <View style={{ flex: 1, backgroundColor: 'black', justifyContent: 'center' }}>
          <WebView
            style={{ flex: 1, backgroundColor: 'black' }}
            source={{ html: `<html><body style="margin:0;padding:0;background-color:black;display:flex;justify-content:center;align-items:center;"><img src="${streamUrl}" style="width:100%;height:100%;object-fit:contain;" /></body></html>` }}
            scrollEnabled={false}
          />
          <TouchableOpacity 
            onPress={() => setIsFullScreen(false)} 
            style={{ position: 'absolute', top: 50, right: 20, backgroundColor: 'rgba(255,255,255,0.3)', padding: 10, borderRadius: 30, zIndex: 9999, elevation: 15 }}
          >
            <Ionicons name="close" size={28} color="white" />
          </TouchableOpacity>
        </View>
      </Modal>
    </View>
  );
}
