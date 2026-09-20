export type SlotStatus = "FREE" | "ASSIGNED" | "OCCUPIED" | "WRONG_VEHICLE" | "FAULT";

export interface ParkingSlot {
  slot_id: "A1" | "A2" | "B1" | "B2";
  status: SlotStatus;
  assigned_session_id?: string | null;
  current_plate?: string | null;
  entry_time?: string | null;
  updated_at: string;
}

export interface ParkingSession {
  session_id: string;
  plate_number: string;
  slot_id: "A1" | "A2" | "B1" | "B2";
  status: "ACTIVE" | "COMPLETED" | "REJECTED" | "REVIEW_REQUIRED";
  entry_time: string;
  exit_time?: string | null;
}

export interface ReviewRequest {
  request_id: string;
  session_id: string;
  plate_number: string;
  reason_code: string;
  similarity_score: number;
  status: "PENDING" | "APPROVED" | "REJECTED";
  created_at: string;
}

export interface SystemEventLog {
  id: string;
  type: string;
  title: string;
  description: string;
  timestamp: string;
  severity: "info" | "warning" | "success" | "error";
}