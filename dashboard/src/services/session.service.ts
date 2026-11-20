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
  overall_status: "HEALTHY" | "DEGRADED_OR_STALE";
  slot_stale_seconds: number;
  sensors: DeviceSensorHealth[];
  server_time: string;
  server_time_vn: string;
}

export class SessionService {
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
