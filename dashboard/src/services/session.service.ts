import { ref, onValue } from "firebase/database";
import { db } from "./firebase";
import { ParkingSession } from "../shared/types";

export const initialSessions: ParkingSession[] = [
  { session_id: "SES-20260920-001", plate_number: "43A-123.45", slot_id: "A1", status: "ACTIVE", entry_time: "14:20:10" },
  { session_id: "SES-20260920-002", plate_number: "92B-678.90", slot_id: "B1", status: "ACTIVE", entry_time: "14:42:05" },
];

export class SessionService {
  static subscribeSessions(callback: (sessions: ParkingSession[]) => void): () => void {
    if (!db) {
      callback(initialSessions);
      return () => {};
    }

    try {
      const sesRef = ref(db, "parking_sessions");
      const unsubscribe = onValue(sesRef, (snapshot) => {
        const data = snapshot.val();
        if (data) {
          callback(Object.values(data));
        } else {
          callback(initialSessions);
        }
      });
      return unsubscribe;
    } catch {
      callback(initialSessions);
      return () => {};
    }
  }
}