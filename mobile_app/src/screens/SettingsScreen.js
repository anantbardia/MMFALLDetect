import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, Switch, TouchableOpacity, Share, TextInput } from 'react-native';
import { useTheme } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { logoutUser, auth } from '../services/firebaseAuth';
import notificationService from '../services/notificationService';

export default function SettingsScreen({ toggleTheme, isDarkTheme }) {
  const { colors } = useTheme();
  const [pushEnabled, setPushEnabled] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);
  const [pushToken, setPushToken] = useState('Fetching token...');
  const [baseUrl, setBaseUrl] = useState('https://mmfalldetect.onrender.com');
  const [cameraUrl, setCameraUrl] = useState('https://crouch-trapped-stock.ngrok-free.dev');
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    // Fetch logged in Firebase user details
    const user = auth.currentUser;
    if (user) {
      setCurrentUser(user);
    }

    // Load active push notification token
    if (notificationService.expoPushToken) {
      setPushToken(notificationService.expoPushToken);
    } else {
      notificationService.registerForPushNotificationsAsync()
        .then(token => {
          if (token) setPushToken(token);
          else setPushToken('Unavailable (Requires Device)');
        });
    }

    // Load URLs
    const loadUrls = async () => {
      try {
        const savedBaseUrl = await AsyncStorage.getItem('baseUrl');
        const savedCameraUrl = await AsyncStorage.getItem('cameraUrl');
        if (savedBaseUrl) setBaseUrl(savedBaseUrl);
        if (savedCameraUrl) setCameraUrl(savedCameraUrl);
      } catch (e) {
        console.error('Failed to load URLs', e);
      }
    };
    loadUrls();
  }, []);

  const handleSaveUrls = async () => {
    try {
      await AsyncStorage.setItem('baseUrl', baseUrl);
      await AsyncStorage.setItem('cameraUrl', cameraUrl);
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 2000);
      import('react-native').then(rn => rn.Alert.alert('Settings Saved', 'Please restart the app for the new URLs to take effect.'));
    } catch (e) {
      console.error('Failed to save URLs', e);
    }
  };

  const handleShareToken = async () => {
    try {
      await Share.share({
        message: pushToken,
      });
    } catch (error) {
      console.error(error.message);
    }
  };

  const handleLogout = async () => {
    try {
      await logoutUser();
    } catch (e) {
      console.error('Logout failed:', e);
    }
  };

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
    sectionTitle: {
      fontSize: 16,
      fontWeight: 'bold',
      color: colors.textSecondary,
      marginTop: 16,
      marginBottom: 8,
      textTransform: 'uppercase',
      letterSpacing: 1,
    },
    settingCard: {
      backgroundColor: colors.surface,
      borderRadius: 16,
      elevation: 2,
      shadowColor: colors.cardShadow,
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.1,
      shadowRadius: 8,
      marginBottom: 20,
      borderWidth: 1,
      borderColor: colors.border,
      overflow: 'hidden',
    },
    settingRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: 16,
      borderBottomWidth: 1,
      borderBottomColor: colors.border,
    },
    settingText: {
      fontSize: 15,
      color: colors.text,
      fontWeight: '500',
    },
    settingSubText: {
      fontSize: 11,
      color: colors.textSecondary,
      marginTop: 2,
    },
    logoutButton: {
      backgroundColor: colors.danger + '15',
      borderRadius: 14,
      paddingVertical: 14,
      alignItems: 'center',
      marginTop: 10,
      borderWidth: 1,
      borderColor: colors.danger + '35',
    },
    logoutText: {
      color: colors.danger,
      fontSize: 16,
      fontWeight: 'bold',
    },
    urlInput: {
      backgroundColor: colors.surface,
      borderColor: colors.primary,
      borderWidth: 1,
      borderRadius: 8,
      padding: 12,
      color: colors.text,
      marginBottom: 16,
      marginTop: 4,
      fontSize: 14,
    },
    saveButton: {
      backgroundColor: colors.primary,
      borderRadius: 8,
      padding: 12,
      alignItems: 'center',
      marginTop: 4,
    }
  });

  return (
    <View style={styles.container}>
      <Text style={styles.header}>Settings</Text>

      {/* User Information Profile */}
      <Text style={styles.sectionTitle}>Account Profiles</Text>
      <View style={styles.settingCard}>
        <View style={styles.settingRow}>
          <View>
            <Text style={styles.settingText}>Logged in as</Text>
            <Text style={[styles.settingSubText, { fontSize: 13, color: colors.primary, fontWeight: 'bold' }]}>
              {currentUser ? currentUser.email : 'Guest User'}
            </Text>
          </View>
        </View>
      </View>

      {/* App Customizations Settings */}
      <Text style={styles.sectionTitle}>Preferences</Text>
      <View style={styles.settingCard}>
        <View style={styles.settingRow}>
          <View>
            <Text style={styles.settingText}>Dark Mode</Text>
            <Text style={styles.settingSubText}>Toggle light and dark color schemes</Text>
          </View>
          <Switch
            value={isDarkTheme}
            onValueChange={toggleTheme}
            trackColor={{ false: '#767577', true: colors.primary }}
            thumbColor={isDarkTheme ? '#fff' : '#f4f3f4'}
          />
        </View>

        <View style={styles.settingRow}>
          <View>
            <Text style={styles.settingText}>Push Notifications</Text>
            <Text style={styles.settingSubText}>Receive alarms for fall detection events</Text>
          </View>
          <Switch
            value={pushEnabled}
            onValueChange={setPushEnabled}
            trackColor={{ false: '#767577', true: colors.primary }}
            thumbColor={pushEnabled ? '#fff' : '#f4f3f4'}
          />
        </View>
      </View>

      {/* Network Configuration */}
      <Text style={styles.sectionTitle}>Network Configuration</Text>
      <View style={[styles.settingCard, { padding: 16 }]}>
        <Text style={styles.settingText}>Backend API URL (WebSockets)</Text>
        <TextInput 
          style={styles.urlInput} 
          value={baseUrl} 
          onChangeText={setBaseUrl} 
          placeholder="https://mmfalldetect.onrender.com" 
          placeholderTextColor={colors.textSecondary}
        />
        
        <Text style={styles.settingText}>Camera Feed URL (Ngrok)</Text>
        <TextInput 
          style={styles.urlInput} 
          value={cameraUrl} 
          onChangeText={setCameraUrl} 
          placeholder="https://xxxx.ngrok-free.dev" 
          placeholderTextColor={colors.textSecondary}
        />
        
        <TouchableOpacity style={styles.saveButton} onPress={handleSaveUrls}>
          <Text style={{ color: 'white', fontWeight: 'bold' }}>{isSaved ? 'Saved!' : 'Save URLs'}</Text>
        </TouchableOpacity>
      </View>

      {/* Cloud Integration Push Token Info */}
      <Text style={styles.sectionTitle}>Push Token Integration</Text>
      <View style={styles.settingCard}>
        <TouchableOpacity style={styles.settingRow} onPress={handleShareToken}>
          <View style={{ flex: 1, marginRight: 8 }}>
            <Text style={styles.settingText}>Expo Push Token</Text>
            <Text style={[styles.settingSubText, { fontSize: 12 }]} numberOfLines={1}>
              {pushToken}
            </Text>
          </View>
          <Text style={{ color: colors.primary, fontSize: 13, fontWeight: 'bold' }}>Copy</Text>
        </TouchableOpacity>
      </View>

      {/* User Logout Button */}
      <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
        <Text style={styles.logoutText}>Sign Out</Text>
      </TouchableOpacity>
    </View>
  );
}
