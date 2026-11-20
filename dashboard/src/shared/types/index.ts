export type SlotId = "A1" | "A2" | "B1" | "B2";

export type PhysicalSlotStatus = "Free" | "Occupied" | "Unknown" | "Fault";

export type DisplaySlotStatus =
  | "AVAILABLE"
  | "RESERVED"
  | "ASSIGNED_PENDING"
  | "OCCUPIED"
  | "UNKNOWN_OR_FAULT";

export type BookingStatus =
  | "Reserved"
  | "Checkin_pending"
  | "Checked_in"
  | "Completed"
  | "Expired"
  | "Cancelled";

export type SessionStatus =
  | "Entry_pending"
  | "Active"
  | "Exit_pending"
  | "Closed"
  | "Cancelled";

export type ParkingStatus =
  | "Not_arrived"
  | "Parking_pending"
  | "Parked_confirmed"
  | "Parking_review_required"
  | "Parking_timeout";

export interface UserVehicle {
  vehicle_id: number;
  plate_number: string;
  plate_display: string;
  status: "Active" | "Disabled";
}

export interface UserFaceTemplateInfo {
  has_active_template: boolean;
  template_id: number | null;
  model_id: string | null;
  model_version: string | null;
  liveness_status: string | null;
  status: string | null;
  updated_at: string | null;
  updated_at_vn: string | null;
}

export interface UserProfile {
  user_id: number;
  username: string;
  display_name: string;
  role: "user" | "admin";
  status: "Active" | "Disabled";
  vehicles: UserVehicle[];
  face_template: UserFaceTemplateInfo;
  server_time?: string;
}

export interface ParkingSlotView {
  slot_id: SlotId;
  sensor_id: string;
  physical_status: PhysicalSlotStatus;
  display_status: DisplaySlotStatus;
  label_vi: string;
  is_available: boolean;
  is_bookable: boolean;
  sensor_fresh: boolean;
  is_my_booking: boolean;
  is_my_session: boolean;
  booking_id: string | null;
  booking_status: BookingStatus | null;
  expires_at: string | null;
  expires_at_vn: string | null;
  remaining_seconds: number | null;
  plate_number: string | null;
  plate_display: string | null;
  updated_at: string | null;
  updated_at_vn: string | null;
  last_seen_at: string | null;
  last_seen_at_vn: string | null;
  // Admin-only fields
  active_booking_id?: string | null;
  reserved_session_id?: string | null;
  session_status?: SessionStatus | null;
  parking_status?: ParkingStatus | null;
  entry_time?: string | null;
  entry_time_vn?: string | null;
  booked_by_user_id?: number | null;
  booked_by_username?: string | null;
  booked_by_display_name?: string | null;
  last_boot_id?: string | null;
  last_sequence?: number | null;
}

export interface SlotsResponse {
  slots: ParkingSlotView[];
  available_count: number;
  total_count: number;
  slot_stale_seconds: number;
  server_time: string;
  server_time_vn: string;
}

export interface BookingDTO {
  booking_id: string;
  user_id: number;
  vehicle_id: number;
  plate_number: string | null;
  plate_display: string | null;
  slot_id: SlotId;
  status: BookingStatus;
  created_at: string;
  created_at_vn: string;
  expires_at: string;
  expires_at_vn: string;
  checkin_started_at: string | null;
  checked_in_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  checkin_event_id: string | null;
  remaining_seconds: number;
  can_cancel: boolean;
  server_time: string;
  server_time_vn: string;
  session_id?: string | null;
  session_status?: SessionStatus | null;
  parking_status?: ParkingStatus | null;
  entry_time?: string | null;
  entry_time_vn?: string | null;
  username?: string;
  display_name?: string;
}

export interface SessionDTO {
  session_id: string;
  plate_number: string;
  plate_display: string;
  user_id?: number | null;
  username?: string | null;
  display_name?: string | null;
  vehicle_id?: number | null;
  booking_id: string | null;
  booking_status?: BookingStatus | null;
  booking_expires_at?: string | null;
  booking_expires_at_vn?: string | null;
  booking_remaining_seconds?: number;
  assigned_slot_id: SlotId;
  status: SessionStatus;
  parking_status: ParkingStatus;
  ocr_confidence: number | null;
  entry_time: string | null;
  entry_time_vn: string | null;
  exit_time: string | null;
  exit_time_vn: string | null;
  created_at: string | null;
  created_at_vn: string | null;
}

export interface ManualReviewItem {
  review_type: "GATE_EVENT" | "PARKING_ANOMALY";
  event_id: string;
  gate_id: "IN" | "OUT";
  device_id: string;
  session_id: string | null;
  booking_id: string | null;
  plate_number: string | null;
  plate_display: string | null;
  slot_id: SlotId | null;
  decision: "Pending" | "Approved" | "Denied" | "Review_required";
  passage_status: string;
  reason_code: string | null;
  liveness_status: string | null;
  liveness_score: number | null;
  reviewer_id: number | null;
  reviewer_username: string | null;
  review_reason: string | null;
  created_at: string | null;
  created_at_vn: string | null;
  decided_at: string | null;
}

export interface DeviceSensorHealth {
  slot_id: SlotId;
  sensor_id: string;
  physical_status: PhysicalSlotStatus;
  is_fresh: boolean;
  is_fault: boolean;
  age_seconds: number | null;
  stale_threshold_seconds: number;
  last_boot_id: string | null;
  last_sequence: number | null;
  last_seen_at: string | null;
  last_seen_at_vn: string | null;
}

export interface RealtimeEnvelope {
  event_type: string;
  server_time: string;
  server_time_vn?: string;
  payload: Record<string, unknown>;
}

// Legacy type aliases kept so any auxiliary subcomponents compile cleanly
export type SlotStatus = "FREE" | "ASSIGNED" | "OCCUPIED" | "WRONG_VEHICLE" | "FAULT";
export interface ParkingSlot {
  slot_id: SlotId;
  status: SlotStatus;
  assigned_session_id?: string | null;
  current_plate?: string | null;
  entry_time?: string | null;
  updated_at: string;
}
export interface ParkingSession {
  session_id: string;
  plate_number: string;
  slot_id: SlotId;
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
