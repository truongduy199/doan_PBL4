import { ApiClient } from "./api.client";
import { BookingDTO, DeviceSensorHealth, SessionDTO } from "../shared/types";

export interface AdminSessionsResponse {
  sessions: SessionDTO[];
  count: number;
  server_time: string;
  server_time_vn: string;
}

export interface AdminBookingsResponse {
  bookings: BookingDTO[];
  count: number;
  server_time: string;
  server_time_vn: string;
}

export interface AdminDevicesResponse {
  gateway?: GatewayStatus;
  mqtt?: { enabled: boolean; connected: boolean; last_error?: string | null };
  overall_status: "HEALTHY" | "DEGRADED_OR_STALE";
  slot_stale_seconds: number;
  sensors: DeviceSensorHealth[];
  server_time: string;
  server_time_vn: string;
}

export interface GatewayStatus {
  ai_status: string;
  active_event_id: string | null;
  queue_length: number;
  devices: { device_id: string; online: boolean; camera_ready?: boolean; age_seconds: number | null }[];
  turns: { event_id: string; gate_id: string; state: string; created_at: string }[];
  commands: { command_id: string; event_id: string; action: string; delivery_status: string; servo_command_issued?: boolean }[];
}

export interface AuditLogDTO {
  log_id: number;
  event_type: string;
  event_id: string | null;
  reason_code: string | null;
  actor_user_id: number | null;
  created_at: string;
}

export class SessionService {
  static async listAdminLogs(): Promise<{ logs: AuditLogDTO[] }> {
    return ApiClient.get<{ logs: AuditLogDTO[] }>("/api/admin/logs?limit=50");
  }
  static async listAdminSessions(status?: string): Promise<AdminSessionsResponse> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return ApiClient.get<AdminSessionsResponse>(`/api/admin/sessions${qs}`);
  }

  static async listAdminBookings(status?: string): Promise<AdminBookingsResponse> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return ApiClient.get<AdminBookingsResponse>(`/api/admin/bookings${qs}`);
  }

  static async getAdminDevices(): Promise<AdminDevicesResponse> {
    return ApiClient.get<AdminDevicesResponse>("/api/admin/devices");
  }
}
