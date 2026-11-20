import React, { useCallback, useEffect, useState } from "react";
import { ApiClient, ApiError } from "../../services/api.client";
import { ParkingService } from "../../services/parking.service";
import { ReviewService } from "../../services/review.service";
import { SessionService } from "../../services/session.service";
import {
  BookingDTO,
  DeviceSensorHealth,
  ManualReviewItem,
  ParkingSlotView,
  SessionDTO,
  UserProfile,
} from "../../shared/types";

interface AdminDashboardPageProps {
  user: UserProfile;
  onLogout: () => void;
}

function formatAdminVnDateTime(isoStr: string | null | undefined): string {
  if (!isoStr) return "—";
  try {
    const dt = new Date(isoStr);
    if (Number.isNaN(dt.getTime())) return isoStr;
    return dt.toLocaleString("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh",
      hour12: false,
    });
  } catch {
    return isoStr;
  }
}

export const AdminDashboardPage: React.FC<AdminDashboardPageProps> = ({
  user,
  onLogout,
}) => {
  const [activeTab, setActiveTab] = useState<
    "overview" | "sessions" | "bookings" | "reviews" | "devices"
  >("overview");

  const [slots, setSlots] = useState<ParkingSlotView[]>([]);
  const [availableCount, setAvailableCount] = useState<number>(0);
  const [sessions, setSessions] = useState<SessionDTO[]>([]);
  const [bookings, setBookings] = useState<BookingDTO[]>([]);
  const [reviews, setReviews] = useState<ManualReviewItem[]>([]);
  const [sensors, setSensors] = useState<DeviceSensorHealth[]>([]);
  const [overallDeviceStatus, setOverallDeviceStatus] = useState<string>("UNKNOWN");
  const [reviewReasons, setReviewReasons] = useState<Record<string, string>>({});

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [realtimeOnline, setRealtimeOnline] = useState<boolean>(false);

  const loadAdminData = useCallback(async () => {
    try {
      const [slotsRes, sessRes, bookRes, revRes, devRes] = await Promise.all([
        ParkingService.getSlots(),
        SessionService.listAdminSessions(),
        SessionService.listAdminBookings(),
        ReviewService.listAdminReviews(false),
        SessionService.getAdminDevices(),
      ]);
      setSlots(slotsRes.slots);
      setAvailableCount(slotsRes.available_count);
      setSessions(sessRes.sessions);
      setBookings(bookRes.bookings);
      setReviews(revRes.reviews);
      setSensors(devRes.sensors);
      setOverallDeviceStatus(devRes.overall_status);
      setApiError(null);
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(`[${err.reasonCode}] ${err.message}`);
      } else {
        setApiError("Không thể kết nối tới FastAPI Backend để tải dữ liệu Quản trị.");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAdminData();
  }, [loadAdminData]);

  useEffect(() => {
    const unsub = ApiClient.subscribeRealtime(
      () => {
        loadAdminData();
      },
      (connected) => setRealtimeOnline(connected)
    );
    return () => unsub();
  }, [loadAdminData]);

  const handleReviewDecision = async (
    eventId: string,
    action: "APPROVE" | "DENY"
  ) => {
    const reason =
      (reviewReasons[eventId] || "").trim() ||
      (action === "APPROVE"
        ? "Quản trị viên xác nhận hợp lệ cho phép qua cổng"
        : "Quản trị viên từ chối qua cổng");
    try {
      await ReviewService.submitDecision(eventId, action, reason);
      setActionFeedback(
        `Đã ghi nhận quyết định ${action} cho sự kiện ${eventId} vào MySQL.`
      );
      await loadAdminData();
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(`[${err.reasonCode}] ${err.message}`);
      }
    }
  };

  const activeSessionsCount = sessions.filter((s) =>
    ["Entry_pending", "Active", "Exit_pending"].includes(s.status)
  ).length;
  const activeBookingsCount = bookings.filter((b) =>
    ["Reserved", "Checkin_pending"].includes(b.status)
  ).length;

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 text-slate-800">
      {/* Top Admin Header */}
      <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-30 shadow-md">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-amber-400 text-slate-950 font-black flex flex-col items-center justify-center">
              <span className="text-sm leading-none">PBL4</span>
              <span className="text-[8px] font-bold mt-0.5">ADMIN</span>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-amber-300 font-bold">
                Trung Tâm Điều Hành Quản Trị • MySQL/InnoDB Single Source of Truth
              </div>
              <h1 className="text-base sm:text-lg font-extrabold">
                Giám Sát 4 Ô Đỗ, Đặt Chỗ, Phiên Xe &amp; Duyệt Ngoại Lệ
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-xs bg-slate-800 border border-slate-700 px-3 py-1.5 rounded-xl">
              Realtime:{" "}
              <strong className={realtimeOnline ? "text-emerald-400" : "text-amber-400"}>
                {realtimeOnline ? "WebSocket Online" : "Polling"}
              </strong>
            </span>
            <span className="text-xs bg-slate-800 border border-slate-700 px-3 py-1.5 rounded-xl">
              Cảm biến IR:{" "}
              <strong
                className={
                  overallDeviceStatus === "HEALTHY"
                    ? "text-emerald-400"
                    : "text-rose-400"
                }
              >
                {overallDeviceStatus}
              </strong>
            </span>
            <div className="text-xs bg-blue-950 border border-blue-800 px-3 py-1.5 rounded-xl font-bold">
              🛡️ {user.display_name} ({user.username})
            </div>
            <button
              onClick={onLogout}
              className="bg-rose-600 hover:bg-rose-500 text-white font-bold px-3 py-1.5 rounded-xl text-xs transition cursor-pointer"
            >
              Đăng xuất
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="bg-[#004b87] border-t border-blue-800">
          <div className="max-w-7xl mx-auto px-4 flex items-center gap-1 overflow-x-auto text-xs font-bold uppercase">
            {(
              [
                { id: "overview", label: "📊 Tổng Quan 4 Ô & Vận Hành" },
                { id: "sessions", label: `🚗 Phiên Xe (${activeSessionsCount})` },
                { id: "bookings", label: `📅 Đặt Chỗ (${activeBookingsCount})` },
                { id: "reviews", label: `🔍 Duyệt Thủ Công (${reviews.length})` },
                { id: "devices", label: "📡 Cảm Biến IR & Thiết Bị" },
              ] as const
            ).map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`px-4 py-3 border-b-2 transition cursor-pointer whitespace-nowrap ${
                  activeTab === t.id
                    ? "bg-[#003366] text-white border-amber-400"
                    : "border-transparent text-blue-100 hover:bg-[#003968]"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </nav>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 flex-1 w-full space-y-6">
        {apiError && (
          <div
            role="alert"
            className="bg-rose-50 border-2 border-rose-500 text-rose-900 p-4 rounded-2xl text-xs font-bold flex items-center justify-between"
          >
            <span>🚨 Lỗi API / Dữ liệu: {apiError}</span>
            <button
              onClick={loadAdminData}
              className="bg-rose-700 text-white px-3 py-1.5 rounded-xl"
            >
              Thử lại
            </button>
          </div>
        )}

        {actionFeedback && (
          <div className="bg-emerald-50 border border-emerald-400 text-emerald-900 p-3.5 rounded-2xl text-xs font-bold flex items-center justify-between">
            <span>✓ {actionFeedback}</span>
            <button onClick={() => setActionFeedback(null)}>✕</button>
          </div>
        )}

        {/* KPI Summary Row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs">
            <div className="text-xs font-bold text-slate-500 uppercase">
              Ô Đỗ Khả Dụng
            </div>
            <div className="text-3xl font-black text-emerald-700 mt-1">
              {availableCount} <span className="text-sm font-medium text-slate-400">/ 4</span>
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs">
            <div className="text-xs font-bold text-slate-500 uppercase">
              Booking Đang Giữ Ô
            </div>
            <div className="text-3xl font-black text-amber-600 mt-1">
              {activeBookingsCount}
            </div>
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-xs">
            <div className="text-xs font-bold text-slate-500 uppercase">
              Phiên Xe Chưa Kết Thúc
            </div>
            <div className="text-3xl font-black text-[#004b87] mt-1">
              {activeSessionsCount}
            </div>
          </div>
          <div className="bg-amber-50 border-2 border-amber-400 rounded-2xl p-4 shadow-xs">
            <div className="text-xs font-bold text-amber-900 uppercase">
              Cần Duyệt Thủ Công
            </div>
            <div className="text-3xl font-black text-amber-800 mt-1">
              {reviews.length}
            </div>
          </div>
        </div>

        {/* 4 Slots Detailed Admin Grid (Always visible on Overview) */}
        {(activeTab === "overview" || activeTab === "devices") && (
          <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
            <h2 className="text-base font-extrabold text-[#004b87] uppercase">
              Trạng Thái Chi Tiết 4 Ô Đỗ (Quyền ADMIN - Hiển Thị Đầy Đủ)
            </h2>
            {isLoading ? (
              <div className="py-8 text-center text-xs text-slate-500">
                Đang tải dữ liệu...
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                {slots.map((s) => (
                  <div
                    key={s.slot_id}
                    className="border-2 border-slate-200 rounded-2xl p-4 space-y-2 bg-slate-50/60"
                  >
                    <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                      <span className="text-2xl font-black text-slate-900">
                        {s.slot_id}
                      </span>
                      <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-[#004b87] text-white">
                        {s.label_vi}
                      </span>
                    </div>
                    <div className="text-xs space-y-1 text-slate-700">
                      <div>
                        Cảm biến ({s.sensor_id}):{" "}
                        <strong>{s.physical_status}</strong>{" "}
                        {s.sensor_fresh ? "(Mới)" : "(Quá hạn/Chưa có)"}
                      </div>
                      <div>
                        Biển số:{" "}
                        <strong className="font-mono text-slate-900">
                          {s.plate_display || s.plate_number || "—"}
                        </strong>
                      </div>
                      <div>
                        Người đặt:{" "}
                        <strong>
                          {s.booked_by_display_name || s.booked_by_username || "—"}
                        </strong>
                      </div>
                      <div>
                        Booking ID:{" "}
                        <span className="font-mono text-[11px]">
                          {s.active_booking_id || "—"}
                        </span>
                      </div>
                      <div>
                        Session ID:{" "}
                        <span className="font-mono text-[11px]">
                          {s.reserved_session_id || "—"}
                        </span>
                      </div>
                      <div>
                        Hết hạn Booking:{" "}
                        <strong>{formatAdminVnDateTime(s.expires_at)}</strong>
                      </div>
                      <div>
                        IR Last Seen:{" "}
                        <span>{formatAdminVnDateTime(s.last_seen_at)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Manual Reviews Section */}
        {(activeTab === "overview" || activeTab === "reviews") && (
          <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
            <h2 className="text-base font-extrabold text-[#004b87] uppercase">
              Danh Sách Sự Kiện Cần Duyệt Thủ Công ({reviews.length})
            </h2>
            {reviews.length === 0 ? (
              <div className="text-xs text-slate-500 py-4">
                Hiện không có sự kiện cổng hoặc phiên đỗ xe nào cần duyệt thủ công.
              </div>
            ) : (
              <div className="space-y-3">
                {reviews.map((rev) => (
                  <div
                    key={rev.event_id}
                    className="border-2 border-amber-400 bg-amber-50/40 rounded-2xl p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4"
                  >
                    <div className="text-xs space-y-1">
                      <div className="font-extrabold text-sm text-slate-900">
                        [{rev.review_type}] Cổng {rev.gate_id} • Mã sự kiện:{" "}
                        <span className="font-mono">{rev.event_id}</span>
                      </div>
                      <div>
                        Biển số:{" "}
                        <strong className="font-mono">
                          {rev.plate_display || rev.plate_number || "—"}
                        </strong>{" "}
                        • Ô: <strong>{rev.slot_id || "—"}</strong> • Mã lý do:{" "}
                        <strong className="text-rose-700">{rev.reason_code}</strong>
                      </div>
                      <div>
                        Liveness: <strong>{rev.liveness_status || "—"}</strong> (Score:{" "}
                        {rev.liveness_score ?? "—"}) • Thời gian:{" "}
                        {formatAdminVnDateTime(rev.created_at)}
                      </div>
                    </div>

                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                      <input
                        type="text"
                        placeholder="Nhập lý do duyệt / từ chối..."
                        value={reviewReasons[rev.event_id] || ""}
                        onChange={(e) =>
                          setReviewReasons((prev) => ({
                            ...prev,
                            [rev.event_id]: e.target.value,
                          }))
                        }
                        className="px-3 py-2 border border-slate-300 rounded-xl text-xs bg-white min-w-[220px]"
                      />
                      <button
                        onClick={() => handleReviewDecision(rev.event_id, "APPROVE")}
                        className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-3.5 py-2 rounded-xl text-xs cursor-pointer"
                      >
                        ✓ Cho phép (APPROVE)
                      </button>
                      <button
                        onClick={() => handleReviewDecision(rev.event_id, "DENY")}
                        className="bg-rose-600 hover:bg-rose-500 text-white font-bold px-3.5 py-2 rounded-xl text-xs cursor-pointer"
                      >
                        ✕ Từ chối (DENY)
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* Admin Sessions Table */}
        {(activeTab === "overview" || activeTab === "sessions") && (
          <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
            <h2 className="text-base font-extrabold text-[#004b87] uppercase">
              Danh Sách Phiên Gửi Xe ({sessions.length})
            </h2>
            <div className="overflow-x-auto border border-slate-200 rounded-xl">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 font-bold text-slate-600">
                    <th className="py-2.5 px-3">Mã Phiên</th>
                    <th className="py-2.5 px-3">Biển Số</th>
                    <th className="py-2.5 px-3">Ô Đỗ</th>
                    <th className="py-2.5 px-3">Trạng Thái Phiên</th>
                    <th className="py-2.5 px-3">Trạng Thái Đỗ</th>
                    <th className="py-2.5 px-3">Giờ Vào / Giờ Ra</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sessions.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-slate-400">
                        Chưa có phiên gửi xe nào.
                      </td>
                    </tr>
                  ) : (
                    sessions.map((s) => (
                      <tr key={s.session_id} className="hover:bg-slate-50">
                        <td className="py-2.5 px-3 font-mono text-[11px]">
                          {s.session_id.slice(0, 8)}...
                        </td>
                        <td className="py-2.5 px-3 font-mono font-bold">
                          {s.plate_display || s.plate_number}
                        </td>
                        <td className="py-2.5 px-3 font-black text-[#004b87]">
                          {s.assigned_slot_id}
                        </td>
                        <td className="py-2.5 px-3 font-bold">{s.status}</td>
                        <td className="py-2.5 px-3">{s.parking_status}</td>
                        <td className="py-2.5 px-3 text-[11px]">
                          <div>Vào: {formatAdminVnDateTime(s.entry_time)}</div>
                          <div>Ra: {formatAdminVnDateTime(s.exit_time)}</div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Admin Bookings Table */}
        {(activeTab === "overview" || activeTab === "bookings") && (
          <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
            <h2 className="text-base font-extrabold text-[#004b87] uppercase">
              Danh Sách Toàn Bộ Đặt Chỗ ({bookings.length})
            </h2>
            <div className="overflow-x-auto border border-slate-200 rounded-xl">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 font-bold text-slate-600">
                    <th className="py-2.5 px-3">Mã Booking</th>
                    <th className="py-2.5 px-3">Tài Khoản</th>
                    <th className="py-2.5 px-3">Biển Số</th>
                    <th className="py-2.5 px-3">Ô</th>
                    <th className="py-2.5 px-3">Trạng Thái</th>
                    <th className="py-2.5 px-3">Giờ Đặt / Hết Hạn</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {bookings.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-slate-400">
                        Chưa có bản ghi đặt chỗ nào.
                      </td>
                    </tr>
                  ) : (
                    bookings.map((b) => (
                      <tr key={b.booking_id} className="hover:bg-slate-50">
                        <td className="py-2.5 px-3 font-mono text-[11px]">
                          {b.booking_id.slice(0, 8)}...
                        </td>
                        <td className="py-2.5 px-3 font-semibold">
                          {b.display_name || b.username || `User #${b.user_id}`}
                        </td>
                        <td className="py-2.5 px-3 font-mono font-bold">
                          {b.plate_display || b.plate_number}
                        </td>
                        <td className="py-2.5 px-3 font-black text-[#004b87]">
                          {b.slot_id}
                        </td>
                        <td className="py-2.5 px-3 font-bold">{b.status}</td>
                        <td className="py-2.5 px-3 text-[11px]">
                          <div>Đặt: {formatAdminVnDateTime(b.created_at)}</div>
                          <div>Hạn: {formatAdminVnDateTime(b.expires_at)}</div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Devices & IR Sensor Freshness Table */}
        {activeTab === "devices" && (
          <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-xs space-y-4">
            <h2 className="text-base font-extrabold text-[#004b87] uppercase">
              Độ Mới Dữ Liệu Cảm Biến IR 4 Ô Đỗ (ESP32 DevKit)
            </h2>
            <div className="overflow-x-auto border border-slate-200 rounded-xl">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 font-bold text-slate-600">
                    <th className="py-2.5 px-3">Ô</th>
                    <th className="py-2.5 px-3">Mã Cảm Biến</th>
                    <th className="py-2.5 px-3">Trạng Thái Vật Lý</th>
                    <th className="py-2.5 px-3">Độ Mới Dữ Liệu</th>
                    <th className="py-2.5 px-3">Boot ID / Sequence</th>
                    <th className="py-2.5 px-3">Last Seen At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {sensors.map((d) => (
                    <tr key={d.slot_id}>
                      <td className="py-2.5 px-3 font-black">{d.slot_id}</td>
                      <td className="py-2.5 px-3 font-mono">{d.sensor_id}</td>
                      <td className="py-2.5 px-3 font-bold">{d.physical_status}</td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-2 py-0.5 rounded font-bold ${
                            d.is_fresh && !d.is_fault
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-rose-100 text-rose-800"
                          }`}
                        >
                          {d.is_fresh && !d.is_fault
                            ? `Hợp lệ (${d.age_seconds ?? 0}s)`
                            : "Quá hạn / Chưa có dữ liệu"}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px]">
                        {d.last_boot_id || "—"} / seq={d.last_sequence ?? "—"}
                      </td>
                      <td className="py-2.5 px-3">
                        {formatAdminVnDateTime(d.last_seen_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>
    </div>
  );
};
