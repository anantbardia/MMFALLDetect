import React, { useState } from 'react';
import { 
  View, 
  Text, 
  TextInput, 
  TouchableOpacity, 
  StyleSheet, 
  ActivityIndicator, 
  KeyboardAvoidingView, 
  Platform,
  ScrollView,
  Image
} from 'react-native';
import { useTheme } from '@react-navigation/native';
import { loginUser, registerUser } from '../services/firebaseAuth';

export default function LoginScreen() {
  const { colors } = useTheme();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isRegistering, setIsRegistering] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const handleAuthAction = async () => {
    if (!email || !password) {
      setErrorMessage('Please fill in all fields.');
      return;
    }
    
    setErrorMessage('');
    setIsLoading(true);
    
    try {
      if (isRegistering) {
        await registerUser(email, password);
      } else {
        await loginUser(email, password);
      }
    } catch (error) {
      console.error(error);
      let cleanMessage = error.message;
      if (error.code === 'auth/email-already-in-use') {
        cleanMessage = 'That email address is already in use!';
      } else if (error.code === 'auth/invalid-email') {
        cleanMessage = 'That email address is invalid!';
      } else if (error.code === 'auth/weak-password') {
        cleanMessage = 'Password should be at least 6 characters.';
      } else if (error.code === 'auth/invalid-credential') {
        cleanMessage = 'Invalid email or password. Please try again.';
      }
      setErrorMessage(cleanMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const styles = StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: colors.background,
    },
    scrollContainer: {
      flexGrow: 1,
      justifyContent: 'center',
      padding: 24,
    },
    brandContainer: {
      alignItems: 'center',
      marginBottom: 40,
    },
    logoText: {
      fontSize: 32,
      fontWeight: 'bold',
      color: colors.primary,
      letterSpacing: 1,
    },
    subtitleText: {
      fontSize: 16,
      color: colors.textSecondary,
      marginTop: 8,
    },
    card: {
      backgroundColor: colors.surface,
      borderRadius: 24,
      padding: 24,
      elevation: 4,
      shadowColor: colors.cardShadow,
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.1,
      shadowRadius: 12,
    },
    headerText: {
      fontSize: 22,
      fontWeight: 'bold',
      color: colors.text,
      marginBottom: 20,
      textAlign: 'center',
    },
    inputLabel: {
      fontSize: 14,
      fontWeight: '600',
      color: colors.textSecondary,
      marginBottom: 8,
      marginLeft: 4,
    },
    input: {
      backgroundColor: colors.background,
      borderColor: colors.border,
      borderWidth: 1,
      borderRadius: 14,
      paddingHorizontal: 16,
      paddingVertical: 14,
      fontSize: 16,
      color: colors.text,
      marginBottom: 16,
    },
    button: {
      backgroundColor: colors.primary,
      borderRadius: 14,
      paddingVertical: 16,
      alignItems: 'center',
      justifyContent: 'center',
      marginTop: 8,
    },
    buttonText: {
      color: '#FFFFFF',
      fontSize: 16,
      fontWeight: 'bold',
    },
    switchContainer: {
      flexDirection: 'row',
      justifyContent: 'center',
      marginTop: 20,
    },
    switchText: {
      color: colors.textSecondary,
      fontSize: 14,
    },
    switchLink: {
      color: colors.primary,
      fontSize: 14,
      fontWeight: 'bold',
      marginLeft: 6,
    },
    errorBox: {
      backgroundColor: colors.danger + '10',
      borderColor: colors.danger + '30',
      borderWidth: 1,
      borderRadius: 12,
      padding: 12,
      marginBottom: 16,
    },
    errorText: {
      color: colors.danger,
      fontSize: 14,
      textAlign: 'center',
      fontWeight: '500',
    }
  });

  return (
    <KeyboardAvoidingView 
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'} 
      style={styles.container}
    >
      <ScrollView contentContainerStyle={styles.scrollContainer} keyboardShouldPersistTaps="handled">
        <View style={styles.brandContainer}>
          <Image source={require('../../assets/logo.png')} style={{ width: 120, height: 120, marginBottom: 16 }} resizeMode="contain" />
          <Text style={styles.logoText}>Fall-o-Up</Text>
          <Text style={styles.subtitleText}>Advanced Fall Detection & Health Monitor</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.headerText}>
            {isRegistering ? 'Create Account' : 'Welcome Back'}
          </Text>

          {errorMessage ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{errorMessage}</Text>
            </View>
          ) : null}

          <Text style={styles.inputLabel}>Email Address</Text>
          <TextInput 
            style={styles.input}
            placeholder="Enter your email"
            placeholderTextColor={colors.textSecondary}
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
          />

          <Text style={styles.inputLabel}>Password</Text>
          <TextInput 
            style={styles.input}
            placeholder="Enter your password"
            placeholderTextColor={colors.textSecondary}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoCapitalize="none"
          />

          <TouchableOpacity 
            style={styles.button} 
            onPress={handleAuthAction}
            disabled={isLoading}
          >
            {isLoading ? (
              <ActivityIndicator color="#FFFFFF" />
            ) : (
              <Text style={styles.buttonText}>
                {isRegistering ? 'Sign Up' : 'Log In'}
              </Text>
            )}
          </TouchableOpacity>

          <View style={styles.switchContainer}>
            <Text style={styles.switchText}>
              {isRegistering ? 'Already have an account?' : "Don't have an account?"}
            </Text>
            <TouchableOpacity onPress={() => setIsRegistering(!isRegistering)}>
              <Text style={styles.switchLink}>
                {isRegistering ? 'Log In' : 'Sign Up'}
              </Text>
            </TouchableOpacity>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
