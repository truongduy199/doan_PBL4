// Firebase initialization with graceful fallback
import { initializeApp, getApps } from "firebase/app";
import { getDatabase, Database } from "firebase/database";
import { getAuth, Auth } from "firebase/auth";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "mock-api-key",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "smart-parking-pbl4.firebaseapp.com",
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL || "https://smart-parking-pbl4-default-rtdb.firebaseio.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "smart-parking-pbl4",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "smart-parking-pbl4.appspot.com",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "123456789",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:123456789:web:mockapp"
};

let db: Database | null = null;
let auth: Auth | null = null;

try {
  const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
  db = getDatabase(app);
  auth = getAuth(app);
} catch (e) {
  console.warn("Firebase not fully configured, running in local state mode:", e);
}

export { db, auth };