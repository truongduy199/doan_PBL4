import { ApiClient } from "./api.client";
import { BookingDTO, SessionDTO, SlotId, SlotsResponse } from "../shared/types";

export interface CurrentBookingResponse {
  booking: BookingDTO | null;
  server_time: string;
  server_time_vn: string;
}

export interface UserHistoryResponse {
  bookings: BookingDTO[];
  sessions: SessionDTO[];
  limit: number;
  offset: number;
  server_time: string;
  server_time_vn: string;
}

export class ParkingService {
  /**
   * Lấy trạng thái 4 ô đỗ (A1, A2, B1, B2) kèm server_time từ FastAPI + MySQL.
   */
  static async getSlots(): Promise<SlotsResponse> {
    return ApiClient.get<SlotsResponse>("/api/slots");
  }

  /**
   * Đặt giữ ô 60 phút cho xe định danh của USER đang đăng nhập.
   */
  static async createBooking(
    vehicleId: number,
    slotId: SlotId,
    idempotencyKey?: string
  ): Promise<BookingDTO> {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers["X-Idempotency-Key"] = idempotencyKey;
    }
    return ApiClient.post<BookingDTO>(
      "/api/bookings",
      {
        vehicle_id: vehicleId,
        slot_id: slotId,
        idempotency_key: idempotencyKey,
      },
      headers
    );
  }

  /**
   * Lấy booking đang hiệu lực của USER kèm server_time để đồng bộ đồng hồ đếm ngược khi F5.
   */
  static async getCurrentBooking(): Promise<CurrentBookingResponse> {
    return ApiClient.get<CurrentBookingResponse>("/api/bookings/current");
  }

  /**
   * Hủy đặt chỗ khi còn ở trạng thái Reserved và chưa bước vào lượt check-in tại cổng.
   */
  static async cancelBooking(bookingId: string): Promise<BookingDTO> {
    return ApiClient.post<BookingDTO>(`/api/bookings/${bookingId}/cancel`);
  }

  /**
   * Lấy lịch sử đặt chỗ và lịch sử gửi xe của chính USER đang đăng nhập.
   */
  static async getMyHistory(params?: {
    bookingStatus?: string;
    sessionStatus?: string;
    limit?: number;
    offset?: number;
  }): Promise<UserHistoryResponse> {
    const q = new URLSearchParams();
    if (params?.bookingStatus) q.set("booking_status", params.bookingStatus);
    if (params?.sessionStatus) q.set("session_status", params.sessionStatus);
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    const qs = q.toString();
    return ApiClient.get<UserHistoryResponse>(
      `/api/me/history${qs ? `?${qs}` : ""}`
    );
  }
}
