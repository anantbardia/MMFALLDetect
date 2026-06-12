import { initializeApp } from 'firebase/app';
import { 
  initializeAuth, 
  getReactNativePersistence,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  onAuthStateChanged
} from 'firebase/auth';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Placeholder Firebase configuration. 
// You can replace these keys with your Firebase project credentials in the Firebase Console!
const firebaseConfig = {
  apiKey: "AIzaSyA7RwoNuwH1R1vq5cW_iBl9VoLMC_e733o",
  authDomain: "mmfalldetect.firebaseapp.com",
  projectId: "mmfalldetect",
  storageBucket: "mmfalldetect.firebasestorage.app",
  messagingSenderId: "75829967535",
  appId: "1:75829967535:web:5ed2e5c2c0a9bd1927725a",
  measurementId: "G-5H9FDQFV3J"
};

// Initialize Firebase App
const app = initializeApp(firebaseConfig);

// Initialize Firebase Auth with persistent storage so users stay logged in
const auth = initializeAuth(app, {
  persistence: getReactNativePersistence(AsyncStorage)
});

export const loginUser = (email, password) => {
  return signInWithEmailAndPassword(auth, email, password);
};

export const registerUser = (email, password) => {
  return createUserWithEmailAndPassword(auth, email, password);
};

export const logoutUser = () => {
  return signOut(auth);
};

export const subscribeToAuthChanges = (callback) => {
  return onAuthStateChanged(auth, callback);
};

export { auth };
export default auth;
