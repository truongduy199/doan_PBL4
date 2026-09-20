import { ref, onValue, set } from "firebase/database";
import { db } from "./firebase";
import { ParkingSlot } from "../shared/types";

export const defaultSlots: ParkingSlot[] = [
  { slot_id: "A1", status: "OCCUPIED", assigned_session_id: "SES-20260920-001", current_plate: "43A-123.45", entry_time: "14:20:10", updated_at: new Date().toISOString() },
  { slot_id: "A2", status: "FREE", assigned_session_id: null, current_plate: null, updated_at: new Date().toISOString() },
  { slot_id: "B1", status: "FREE", assigned_session_id: null, current_plate: null, updated_at: new Date().toISOString() },
  { slot_id: "B2", status: "FREE", assigned_session_id: null, current_plate: null, updated_at: new Date().toISOString() },
];

export class ParkingService {
  /**
   * Lắng nghe thay đổi trạng thái 4 ô đỗ thời gian thực từ Firebase Realtime Database.
   */
  static subscribeSlots(callback: (slots: ParkingSlot[]) => void): () => void {
    if (!db) {
      callback(defaultSlots);
      return () => {};
    }

    try {
      const slotsRef = ref(db, "parking_slots");
      const unsubscribe = onValue(slotsRef, (snapshot) => {
        const data = snapshot.val();
        if (data) {
          let list: ParkingSlot[] = [];
          if (Array.isArray(data)) {
            list = data.filter(Boolean);
          } else if (typeof data === "object") {
            list = Object.values(data);
          }
          // Đảm bảo luôn đủ 4 ô A1, A2, B1, B2 theo đúng thứ tự
          const slotOrder: ("A1" | "A2" | "B1" | "B2")[] = ["A1", "A2", "B1", "B2"];
          const orderedSlots: ParkingSlot[] = slotOrder.map((id) => {
            const found = list.find((s) => s && s.slot_id === id);
            return (
              found || {
                slot_id: id,
                status: "FREE",
                assigned_session_id: null,
                current_plate: null,
                updated_at: new Date().toISOString(),
              }
            );
          });
          callback(orderedSlots);
        } else {
          callback(defaultSlots);
        }
      });
      return unsubscribe;
    } catch (e) {
      console.warn("Could not subscribe to parking_slots:", e);
      callback(defaultSlots);
      return () => {};
    }
  }

  static async updateSlotStatus(slotId: string, status: string): Promise<void> {
    if (!db) return;
    try {
      const slotRef = ref(db, `parking_slots/${slotId}/status`);
      await set(slotRef, status);
    } catch (e) {
      console.warn("Could not update slot status:", e);
    }
  }
}