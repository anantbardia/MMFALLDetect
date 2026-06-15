import React, { useState, useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer, DefaultTheme, DarkTheme } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import { View, ActivityIndicator } from 'react-native';

import LoginScreen from './src/screens/LoginScreen';
import DashboardScreen from './src/screens/DashboardScreen';
import EventsScreen from './src/screens/EventsScreen';
import SettingsScreen from './src/screens/SettingsScreen';
import { lightTheme, darkTheme } from './src/theme/colors';
import notificationService from './src/services/notificationService';
import { subscribeToAuthChanges } from './src/services/firebaseAuth';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

export default function App() {
  const [isDarkTheme, setIsDarkTheme] = useState(false);
  const [user, setUser] = useState(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  useEffect(() => {
    // 1. Load saved theme from storage
    const loadTheme = async () => {
      try {
        const savedTheme = await AsyncStorage.getItem('isDarkTheme');
        if (savedTheme !== null) {
          setIsDarkTheme(JSON.parse(savedTheme));
        }
      } catch (e) {
        console.error('Failed to load theme preference', e);
      }
    };
    loadTheme();

    // 2. Subscribe to Firebase Authentication changes
    const unsubscribeAuth = subscribeToAuthChanges((currentUser) => {
      setUser(currentUser);
      setIsAuthLoading(false);
    });

    // 3. Register for push notifications
    notificationService.registerForPushNotificationsAsync();
    
    // 4. Setup notification listeners
    notificationService.setupListeners((notification) => {
      console.log('Received notification data:', notification.request.content.data);
    });

    return () => {
      unsubscribeAuth();
      notificationService.removeListeners();
    };
  }, []);



  const toggleTheme = async () => {
    const newTheme = !isDarkTheme;
    setIsDarkTheme(newTheme);
    try {
      await AsyncStorage.setItem('isDarkTheme', JSON.stringify(newTheme));
    } catch (e) {
      console.error('Failed to save theme preference', e);
    }
  };

  const CustomDefaultTheme = {
    ...DefaultTheme,
    colors: {
      ...DefaultTheme.colors,
      ...lightTheme,
    },
  };

  const CustomDarkTheme = {
    ...DarkTheme,
    colors: {
      ...DarkTheme.colors,
      ...darkTheme,
    },
  };

  const activeTheme = isDarkTheme ? CustomDarkTheme : CustomDefaultTheme;

  // Show a premium loading spinner while Firebase checks the user session
  if (isAuthLoading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: activeTheme.colors.background }}>
        <ActivityIndicator size="large" color={activeTheme.colors.primary} />
      </View>
    );
  }

  return (
    <NavigationContainer theme={activeTheme}>
      <StatusBar style={isDarkTheme ? 'light' : 'dark'} />
      
      {user ? (
        // Main Application Flow (Protected Screens)
        <Tab.Navigator
          screenOptions={({ route }) => ({
            tabBarIcon: ({ focused, color, size }) => {
              let iconName;

              if (route.name === 'Dashboard') {
                iconName = focused ? 'videocam' : 'videocam-outline';
              } else if (route.name === 'Events') {
                iconName = focused ? 'notifications' : 'notifications-outline';
              } else if (route.name === 'Settings') {
                iconName = focused ? 'options' : 'options-outline';
              }

              return <Ionicons name={iconName} size={size} color={color} />;
            },
            tabBarActiveTintColor: activeTheme.colors.primary,
            tabBarInactiveTintColor: activeTheme.colors.textSecondary,
            tabBarStyle: {
              backgroundColor: activeTheme.colors.tabBar,
              borderTopColor: activeTheme.colors.border,
              height: 60,
              paddingBottom: 8,
            },
            headerStyle: {
              backgroundColor: activeTheme.colors.surface,
              borderBottomColor: activeTheme.colors.border,
              borderBottomWidth: 1,
            },
            headerTintColor: activeTheme.colors.text,
            headerTitleStyle: {
              fontWeight: 'bold',
            }
          })}
        >
          <Tab.Screen name="Dashboard" component={DashboardScreen} />
          <Tab.Screen name="Events" component={EventsScreen} />
          <Tab.Screen name="Settings">
            {() => <SettingsScreen isDarkTheme={isDarkTheme} toggleTheme={toggleTheme} />}
          </Tab.Screen>
        </Tab.Navigator>
      ) : (
        // Authentication Flow (Public Login / Signup)
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          <Stack.Screen name="Login" component={LoginScreen} />
        </Stack.Navigator>
      )}
    </NavigationContainer>
  );
}
