export type SlotStatus = "FREE" | "ASSIGNED" | "OCCUPIED" | "WRONG_VEHICLE" | "FAULT";

export interface ParkingSlot {
  slot_id: string;
  status: SlotStatus;
  assigned_session_id?: string;
  current_plate?: string;
  updated_at: string;
}

export interface ParkingSession {
  session_id: string;
  plate_number: string;
  slot_id: string;
  status: "ACTIVE" | "COMPLETED" | "REJECTED" | "REVIEW_REQUIRED";
  entry_time: string;
  exit_time?: string;
}