import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

// Set up default behavior for incoming notifications when the app is in the foreground
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

class NotificationService {
  constructor() {
    this.expoPushToken = '';
    this.notificationListener = null;
    this.responseListener = null;
  }

  async registerForPushNotificationsAsync(patientId, backendUrl) {
    let token;

    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'default',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#FF231F7C',
      });
    }

    if (Device.isDevice) {
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;
      
      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }
      
      if (finalStatus !== 'granted') {
        console.warn('Failed to get push token for push notification!');
        return;
      }
      
      try {
        const projectId = Constants.expoConfig?.extra?.eas?.projectId || Constants.easConfig?.projectId;
        token = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
        this.expoPushToken = token;
        console.log('Expo Push Token:', token);
        
        if (patientId && backendUrl) {
          try {
            const response = await fetch(`${backendUrl}/api/v1/notifications/register`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ patient_id: patientId, token: token })
            });
            console.log('Push token registered with backend:', response.status);
          } catch (err) {
            console.error('Failed to register push token with backend:', err);
          }
        }
      } catch (e) {
        console.error('Error fetching push token:', e);
      }
    } else {
      console.warn('Must use physical device for Push Notifications');
    }

    return token;
  }

  setupListeners(onNotificationReceived) {
    // This listener is fired whenever a notification is received while the app is foregrounded
    this.notificationListener = Notifications.addNotificationReceivedListener(notification => {
      console.log('Notification Received in foreground:', notification);
      if (onNotificationReceived) {
        onNotificationReceived(notification);
      }
    });

    // This listener is fired whenever a user taps on or interacts with a notification 
    this.responseListener = Notifications.addNotificationResponseReceivedListener(response => {
      console.log('Notification Clicked/Responded:', response);
    });
  }

  removeListeners() {
    if (this.notificationListener) {
      Notifications.removeNotificationSubscription(this.notificationListener);
    }
    if (this.responseListener) {
      Notifications.removeNotificationSubscription(this.responseListener);
    }
  }

  async sendLocalNotification(title, body, data = {}) {
    await Notifications.scheduleNotificationAsync({
      content: {
        title,
        body,
        data,
      },
      trigger: null, // trigger immediately
    });
  }
}

const notificationService = new NotificationService();
export default notificationService;
