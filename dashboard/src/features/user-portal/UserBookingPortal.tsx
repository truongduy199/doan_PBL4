import React, { useCallback, useEffect, useRef, useState } from "react";
import { ApiClient, ApiError } from "../../services/api.client";
import { ParkingService } from "../../services/parking.service";
import {
  BookingDTO,
  DisplaySlotStatus,
  ParkingSlotView,
  SessionDTO,
  SlotId,
  UserProfile,
} from "../../shared/types";
import { FirstPersonDriverModal } from "./FirstPersonDriverModal";

interface UserBookingPortalProps {
  user: UserProfile;
  onLogout: () => void;
}

function formatCountdownMMSS(totalSeconds: number): string {
  const clamped = Math.max(0, Math.floor(totalSeconds));
  const mins = Math.floor(clamped / 60);
  const secs = clamped % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function formatVnDateTime(isoStr: string | null | undefined): string {
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

function getBookingStatusBadge(status: string): { label: string; className: string } {
  switch (status) {
    case "Reserved":
      return {
        label: "Đang giữ chỗ (Reserved)",
        className: "bg-amber-100 text-amber-900 border-amber-300",
      };
    case "Checkin_pending":
      return {
        label: "Đang đối soát cổng vào (Checkin_pending)",
        className: "bg-sky-100 text-sky-900 border-sky-300",
      };
    case "Checked_in":
      return {
        label: "Đã qua cổng vào (Checked_in)",
        className: "bg-indigo-100 text-indigo-900 border-indigo-300",
      };
    case "Completed":
      return {
        label: "Hoàn tất lượt đỗ (Completed)",
        className: "bg-emerald-100 text-emerald-900 border-emerald-300",
      };
    case "Expired":
      return {
        label: "Hết hạn 60 phút (Expired)",
        className: "bg-rose-100 text-rose-900 border-rose-300",
      };
    case "Cancelled":
      return {
        label: "Đã hủy đặt chỗ (Cancelled)",
        className: "bg-slate-200 text-slate-700 border-slate-300",
      };
    default:
      return {
        label: status,
        className: "bg-slate-100 text-slate-700 border-slate-300",
      };
  }
}

export const UserBookingPortal: React.FC<UserBookingPortalProps> = ({
  user,
  onLogout,
}) => {
  const [slots, setSlots] = useState<ParkingSlotView[]>([]);
  const [availableCount, setAvailableCount] = useState<number>(0);
  const [selectedSlotId, setSelectedSlotId] = useState<SlotId | null>(null);
  const [currentBooking, setCurrentBooking] = useState<BookingDTO | null>(null);
  const [historyBookings, setHistoryBookings] = useState<BookingDTO[]>([]);
  const [historySessions, setHistorySessions] = useState<SessionDTO[]>([]);
  const [historyStatusFilter, setHistoryStatusFilter] = useState<string>("");

  // Clock offset: serverTimeMs - Date.now()
  const serverOffsetMsRef = useRef<number>(0);
  const [lastUpdatedVn, setLastUpdatedVn] = useState<string>("—");
  const [countdownSeconds, setCountdownSeconds] = useState<number>(0);

  // Loading & Error / Alert Banner States
  const [isInitialLoading, setIsInitialLoading] = useState<boolean>(true);
  const [isBookingSubmitting, setIsBookingSubmitting] = useState<boolean>(false);
  const [isCancelSubmitting, setIsCancelSubmitting] = useState<boolean>(false);
  const [apiErrorBanner, setApiErrorBanner] = useState<string | null>(null);
  const [feedbackBanner, setFeedbackBanner] = useState<{
    type: "success" | "warning" | "error";
    text: string;
  } | null>(null);
  const [realtimeConnected, setRealtimeConnected] = useState<boolean>(false);

  // First-Person Driver Navigation Modal
  const [isDriverModalOpen, setIsDriverModalOpen] = useState<boolean>(false);

  const primaryVehicle = user.vehicles[0] || null;

  const syncServerTimeOffset = (serverTimeIso?: string) => {
    if (!serverTimeIso) return;
    const parsed = Date.parse(serverTimeIso);
    if (!Number.isNaN(parsed)) {
      serverOffsetMsRef.current = parsed - Date.now();
      setLastUpdatedVn(formatVnDateTime(serverTimeIso));
    }
  };

  const refreshAllData = useCallback(async () => {
    try {
      const [slotsRes, currentRes, historyRes] = await Promise.all([
        ParkingService.getSlots(),
        ParkingService.getCurrentBooking(),
        ParkingService.getMyHistory({
          bookingStatus: historyStatusFilter || undefined,
          limit: 30,
        }),
      ]);

      syncServerTimeOffset(slotsRes.server_time || currentRes.server_time);
      setSlots(slotsRes.slots);
      setAvailableCount(slotsRes.available_count);
      setCurrentBooking(currentRes.booking);
      setHistoryBookings(historyRes.bookings);
      setHistorySessions(historyRes.sessions);
      setApiErrorBanner(null);

      // Default select first bookable slot if none selected
      setSelectedSlotId((prev) => {
        if (prev && slotsRes.slots.some((s) => s.slot_id === prev && s.is_bookable)) {
          return prev;
        }
        const firstBookable = slotsRes.slots.find((s) => s.is_bookable);
        return firstBookable ? firstBookable.slot_id : null;
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setApiErrorBanner(`[${err.reasonCode}] ${err.message}`);
      } else {
        setApiErrorBanner("Mất kết nối tới máy chủ FastAPI. Không thể tải dữ liệu ô đỗ thực tế.");
      }
    } finally {
      setIsInitialLoading(false);
    }
  }, [historyStatusFilter]);

  useEffect(() => {
    refreshAllData();
  }, [refreshAllData]);

  // Realtime WebSocket / SSE listener
  useEffect(() => {
    const unsub = ApiClient.subscribeRealtime(
      () => {
        refreshAllData();
      },
      (connected) => setRealtimeConnected(connected)
    );
    return () => unsub();
  }, [refreshAllData]);

  // Accurate 1-second countdown timer using expires_at - (Date.now() + serverOffsetMs)
  useEffect(() => {
    if (!currentBooking || currentBooking.status !== "Reserved") {
      setCountdownSeconds(0);
      return;
    }

    const expiresMs = Date.parse(currentBooking.expires_at);
    if (Number.isNaN(expiresMs)) {
      setCountdownSeconds(currentBooking.remaining_seconds || 0);
      return;
    }

    const computeRemaining = () => {
      const nowServerMs = Date.now() + serverOffsetMsRef.current;
      const diffSec = Math.max(0, Math.floor((expiresMs - nowServerMs) / 1000));
      setCountdownSeconds(diffSec);
      if (diffSec === 0) {
        // Trigger server refresh when countdown hits 00:00
        refreshAllData();
      }
    };

    computeRemaining();
    const timer = window.setInterval(computeRemaining, 1000);
    return () => window.clearInterval(timer);
  }, [currentBooking, refreshAllData]);

  const handleBookSlot = async () => {
    if (isBookingSubmitting || !selectedSlotId) return;
    if (!primaryVehicle) {
      setFeedbackBanner({
        type: "error",
        text: "Tài khoản chưa có phương tiện định danh hoạt động để đặt chỗ.",
      });
      return;
    }

    setIsBookingSubmitting(true);
    setFeedbackBanner(null);
    const idempotencyKey = `book-${user.user_id}-${primaryVehicle.vehicle_id}-${selectedSlotId}-${Date.now()}`;

    try {
      const created = await ParkingService.createBooking(
        primaryVehicle.vehicle_id,
        selectedSlotId,
        idempotencyKey
      );
      syncServerTimeOffset(created.server_time);
      setCurrentBooking(created);
      setFeedbackBanner({
        type: "success",
        text: `Đặt giữ ô ${created.slot_id} thành công trong 60 phút cho xe ${
          created.plate_display || created.plate_number
        }! Bạn có thể bấm "Xem đường đi" để xem mô phỏng lộ trình góc nhìn người lái.`,
      });
      await refreshAllData();
      setIsDriverModalOpen(true);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setFeedbackBanner({
            type: "warning",
            text: `Xung đột đặt chỗ (HTTP 409 - ${err.reasonCode}): ${err.message}`,
          });
        } else {
          setFeedbackBanner({
            type: "error",
            text: `Lỗi đặt chỗ (${err.reasonCode}): ${err.message}`,
          });
        }
      } else {
        setFeedbackBanner({
          type: "error",
          text: "Không thể thực hiện yêu cầu đặt chỗ.",
        });
      }
      await refreshAllData();
    } finally {
      setIsBookingSubmitting(false);
    }
  };

  const handleCancelBooking = async () => {
    if (!currentBooking || isCancelSubmitting) return;
    setIsCancelSubmitting(true);
    setFeedbackBanner(null);
    try {
      const cancelled = await ParkingService.cancelBooking(currentBooking.booking_id);
      syncServerTimeOffset(cancelled.server_time);
      setFeedbackBanner({
        type: "warning",
        text: `Đã hủy đặt chỗ ô ${cancelled.slot_id} thành công. Ô đỗ đã được trả lại cho hệ thống.`,
      });
      await refreshAllData();
    } catch (err) {
      if (err instanceof ApiError) {
        setFeedbackBanner({
          type: "error",
          text: `Không thể hủy đặt chỗ (${err.reasonCode}): ${err.message}`,
        });
      } else {
        setFeedbackBanner({
          type: "error",
          text: "Lỗi kết nối khi hủy đặt chỗ.",
        });
      }
      await refreshAllData();
    } finally {
      setIsCancelSubmitting(false);
    }
  };

  const getSlotVisualStyle = (
    displayStatus: DisplaySlotStatus,
    isSelected: boolean,
    isMyBooking: boolean
  ) => {
    switch (displayStatus) {
      case "AVAILABLE":
        return {
          cardBorder: isSelected
            ? "border-emerald-600 ring-4 ring-emerald-200 bg-emerald-50/70"
            : "border-emerald-500 bg-white hover:bg-emerald-50/40",
          badgeClass: "bg-emerald-600 text-white border-emerald-700",
          icon: "🟢",
          subNote: "Khả dụng • Có thể đặt giữ chỗ 60 phút",
        };
      case "RESERVED":
        return {
          cardBorder: isMyBooking
            ? "border-amber-500 ring-2 ring-amber-200 bg-amber-50/70"
            : "border-amber-400 bg-amber-50/30 opacity-90",
          badgeClass: "bg-amber-500 text-slate-950 border-amber-600",
          icon: "⏳",
          subNote: isMyBooking
            ? "Ô do chính bạn đặt giữ chỗ"
            : "Đã được người dùng khác đặt trước",
        };
      case "ASSIGNED_PENDING":
        return {
          cardBorder: "border-sky-500 bg-sky-50/40 opacity-90",
          badgeClass: "bg-sky-600 text-white border-sky-700",
          icon: "🚗",
          subNote: "Đang cấp cho xe vừa qua cổng vào",
        };
      case "OCCUPIED":
        return {
          cardBorder: "border-[#004b87] bg-blue-50/30 opacity-90",
          badgeClass: "bg-[#004b87] text-white border-blue-900",
          icon: "🚙",
          subNote: "Đang có phương tiện đỗ trong ô",
        };
      case "UNKNOWN_OR_FAULT":
      default:
        return {
          cardBorder: "border-rose-400 bg-rose-50/40 opacity-90",
          badgeClass: "bg-rose-600 text-white border-rose-700",
          icon: "⚠️",
          subNote: "Chưa đủ dữ liệu cảm biến IR mới hoặc lỗi cảm biến",
        };
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 text-slate-800">
      {/* Top User Portal Header */}
      <header className="bg-[#004b87] text-white shadow-md sticky top-0 z-30 border-b border-blue-950">
        <div className="max-w-6xl mx-auto px-4 py-3 flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-amber-400 text-slate-950 font-black flex flex-col items-center justify-center shadow">
              <span className="text-sm leading-none">PBL4</span>
              <span className="text-[8px] font-bold mt-0.5">USER</span>
            </div>
            <div>
              <div className="text-[11px] text-amber-300 font-bold uppercase tracking-wider">
                Cổng Đặt Chỗ Trực Tuyến • Bãi Đỗ Xe Thông Minh IoT
              </div>
              <h1 className="text-base sm:text-lg font-extrabold tracking-tight">
                Đặt Giữ Ô Đỗ 60 Phút &amp; Dẫn Đường Góc Nhìn Người Lái
              </h1>
            </div>
          </div>

          {/* Account, Vehicle & Face Template Summary Pills */}
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="bg-blue-950/80 border border-blue-700 rounded-xl px-3 py-1.5 text-xs">
              <div className="text-[10px] text-blue-300 uppercase font-bold">Chủ xe định danh</div>
              <div className="font-bold text-white">{user.display_name}</div>
            </div>

            <div className="bg-blue-950/80 border border-blue-700 rounded-xl px-3 py-1.5 text-xs">
              <div className="text-[10px] text-blue-300 uppercase font-bold">Xe đăng ký sẵn</div>
              <div className="font-mono font-black text-amber-300">
                {primaryVehicle
                  ? `${primaryVehicle.plate_display} (${primaryVehicle.plate_number})`
                  : "Chưa gán xe"}
              </div>
            </div>

            <div className="bg-blue-950/80 border border-blue-700 rounded-xl px-3 py-1.5 text-xs">
              <div className="text-[10px] text-blue-300 uppercase font-bold">Mẫu khuôn mặt 512-D</div>
              <div className="font-bold flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full ${
                    user.face_template.has_active_template
                      ? "bg-emerald-400"
                      : "bg-rose-400"
                  }`}
                />
                <span
                  className={
                    user.face_template.has_active_template
                      ? "text-emerald-300"
                      : "text-rose-300"
                  }
                >
                  {user.face_template.has_active_template
                    ? `Đã liên kết (${user.face_template.model_id || "buffalo_l"})`
                    : "Chưa có mẫu"}
                </span>
              </div>
            </div>

            <button
              onClick={onLogout}
              className="bg-rose-600 hover:bg-rose-500 text-white font-bold px-3 py-2 rounded-xl text-xs transition cursor-pointer shadow"
            >
              Đăng xuất
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 py-6 flex-1 w-full space-y-6">
        {/* API Error / Disconnection Alert (Never hides errors or fabricates Free slots!) */}
        {apiErrorBanner && (
          <div
            role="alert"
            className="bg-rose-50 border-2 border-rose-500 text-rose-900 rounded-2xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3"
          >
            <div>
              <div className="font-extrabold text-sm flex items-center gap-2">
                <span>🚨 CẢNH BÁO LỖI KẾT NỐI / DỮ LIỆU:</span>
              </div>
              <p className="text-xs font-medium mt-1">{apiErrorBanner}</p>
            </div>
            <button
              onClick={refreshAllData}
              className="bg-rose-700 hover:bg-rose-600 text-white font-bold px-3.5 py-2 rounded-xl text-xs transition cursor-pointer self-start sm:self-center"
            >
              🔄 Thử tải lại
            </button>
          </div>
        )}

        {/* Operation Feedback Banner */}
        {feedbackBanner && (
          <div
            role="status"
            className={`rounded-2xl p-4 border-2 text-xs font-semibold flex items-center justify-between gap-3 shadow-sm ${
              feedbackBanner.type === "success"
                ? "bg-emerald-50 border-emerald-500 text-emerald-950"
                : feedbackBanner.type === "warning"
                ? "bg-amber-50 border-amber-500 text-amber-950"
                : "bg-rose-50 border-rose-500 text-rose-950"
            }`}
          >
            <span>{feedbackBanner.text}</span>
            <button
              onClick={() => setFeedbackBanner(null)}
              className="text-slate-500 hover:text-slate-900 font-bold px-2 py-1"
            >
              ✕
            </button>
          </div>
        )}

        {/* Active Booking Panel & Live Server-Synchronized Countdown */}
        {currentBooking && (
          <section className="bg-gradient-to-r from-[#003366] via-[#004b87] to-slate-900 text-white rounded-2xl p-5 shadow-lg border-2 border-amber-400">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="bg-amber-400 text-slate-950 text-xs font-black px-2.5 py-0.5 rounded-full uppercase">
                    Đặt Chỗ Hiện Hành
                  </span>
                  <span className="text-xs font-mono text-blue-200">
                    Mã: {currentBooking.booking_id}
                  </span>
                </div>
                <h2 className="text-xl sm:text-2xl font-black flex items-center gap-3 flex-wrap">
                  <span>Ô Đỗ Đã Đặt: {currentBooking.slot_id}</span>
                  <span className="text-sm font-mono bg-white/15 px-3 py-1 rounded-xl border border-white/25 text-amber-300">
                    Biển số: {currentBooking.plate_display || currentBooking.plate_number}
                  </span>
                </h2>
                <div className="text-xs text-blue-100 flex flex-wrap gap-x-5 gap-y-1 pt-1">
                  <span>
                    Trạng thái:{" "}
                    <strong className="text-amber-300">{currentBooking.status}</strong>
                  </span>
                  <span>
                    Thời điểm đặt:{" "}
                    <strong>{formatVnDateTime(currentBooking.created_at)}</strong>
                  </span>
                  <span>
                    Hết hạn lúc:{" "}
                    <strong className="text-amber-300">
                      {formatVnDateTime(currentBooking.expires_at)}
                    </strong>
                  </span>
                </div>
              </div>

              {/* Countdown Timer & Actions */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                {currentBooking.status === "Reserved" && (
                  <div className="bg-slate-950/90 border border-amber-400/60 rounded-2xl px-4 py-2.5 text-center">
                    <div className="text-[10px] uppercase tracking-wider text-amber-300 font-bold">
                      Thời gian giữ ô còn lại
                    </div>
                    <div
                      data-testid="booking-countdown"
                      className="text-3xl font-black font-mono text-amber-400 tracking-wider"
                    >
                      {formatCountdownMMSS(countdownSeconds)}
                    </div>
                  </div>
                )}

                <div className="flex flex-col sm:flex-row gap-2">
                  <button
                    onClick={() => setIsDriverModalOpen(true)}
                    className="bg-amber-400 hover:bg-amber-300 text-slate-950 font-extrabold px-4 py-3 rounded-xl text-xs transition cursor-pointer shadow-md flex items-center justify-center gap-1.5"
                  >
                    <span>🚘</span>
                    <span>Xem đường đi (Góc nhìn người lái)</span>
                  </button>

                  <button
                    onClick={handleCancelBooking}
                    disabled={!currentBooking.can_cancel || isCancelSubmitting}
                    title={
                      currentBooking.can_cancel
                        ? "Hủy giữ chỗ ô này"
                        : "Không thể hủy khi xe đã bắt đầu đối soát tại cổng vào"
                    }
                    className="bg-rose-600 hover:bg-rose-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white font-bold px-4 py-3 rounded-xl text-xs transition cursor-pointer shadow-md"
                  >
                    {isCancelSubmitting ? "⏳ Đang hủy..." : "✕ Hủy đặt chỗ"}
                  </button>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* 4 Parking Slots Map & 60-Minute Booking Action */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-slate-100">
            <div>
              <h2 className="text-base sm:text-lg font-extrabold text-[#004b87] uppercase flex items-center gap-2">
                <span>Sơ Đồ 4 Ô Đỗ Xe Thời Gian Thực (A1, A2, B1, B2)</span>
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Chỉ những ô có cảm biến IR báo Trống ổn định, dữ liệu còn mới và chưa có booking/session mới được phép đặt giữ chỗ 60 phút.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3 text-xs">
              <div className="bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-xl font-bold text-emerald-900">
                Ô có thể nhận xe:{" "}
                <span className="text-base font-black text-emerald-700">
                  {availableCount}
                </span>{" "}
                / 4
              </div>
              <div className="bg-slate-100 border border-slate-200 px-3 py-1.5 rounded-xl text-slate-600 font-medium">
                Cập nhật lúc: <strong>{lastUpdatedVn}</strong>
              </div>
              <div className="flex items-center gap-1.5 text-[11px] font-bold">
                <span
                  className={`w-2 h-2 rounded-full ${
                    realtimeConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
                  }`}
                />
                <span>{realtimeConnected ? "Realtime: Online" : "Realtime: Polling"}</span>
              </div>
            </div>
          </div>

          {/* Color & Vietnamese Label Legend */}
          <div className="flex flex-wrap items-center gap-3 text-xs font-semibold bg-slate-50 p-3 rounded-xl border border-slate-200">
            <span className="text-slate-500 font-bold uppercase text-[11px]">Chú giải trạng thái:</span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-100 text-emerald-900 border border-emerald-300">
              <span>🟢</span> Có thể đặt / Nhận xe
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-amber-100 text-amber-900 border border-amber-300">
              <span>⏳</span> Đã đặt trước
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-sky-100 text-sky-900 border border-sky-300">
              <span>🚗</span> Đang cấp / Chờ xe đỗ
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-100 text-blue-900 border border-blue-300">
              <span>🚙</span> Đang có xe
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-rose-100 text-rose-900 border border-rose-300">
              <span>⚠️</span> Chưa đủ dữ liệu / Lỗi cảm biến
            </span>
          </div>

          {/* 4 Slot Cards Grid */}
          {isInitialLoading ? (
            <div className="py-12 text-center text-sm font-semibold text-slate-500">
              ⏳ Đang tải trạng thái 4 ô đỗ từ MySQL...
            </div>
          ) : slots.length === 0 ? (
            <div className="py-10 text-center bg-rose-50 border border-rose-200 rounded-xl text-xs font-bold text-rose-800">
              ⚠️ Chưa đủ dữ liệu / Lỗi kết nối: Không nhận được danh sách ô đỗ từ máy chủ.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {slots.map((slot) => {
                const isSelected = selectedSlotId === slot.slot_id;
                const style = getSlotVisualStyle(
                  slot.display_status,
                  isSelected,
                  slot.is_my_booking
                );

                return (
                  <div
                    key={slot.slot_id}
                    onClick={() => {
                      if (slot.is_bookable && !currentBooking) {
                        setSelectedSlotId(slot.slot_id);
                      }
                    }}
                    className={`border-2 ${style.cardBorder} rounded-2xl p-4 flex flex-col justify-between min-h-[210px] transition shadow-xs ${
                      slot.is_bookable && !currentBooking
                        ? "cursor-pointer"
                        : "cursor-default"
                    }`}
                  >
                    {/* Card Top: Slot ID & Vietnamese Status Label */}
                    <div className="flex items-start justify-between gap-2 border-b border-slate-200/80 pb-2.5">
                      <div>
                        <span className="text-2xl font-black text-slate-900">
                          {slot.slot_id}
                        </span>
                        <div className="text-[11px] text-slate-500 font-medium">
                          Cảm biến: {slot.sensor_id}
                        </div>
                      </div>
                      <span
                        className={`text-[11px] font-extrabold px-2.5 py-1 rounded-lg border text-right ${style.badgeClass}`}
                      >
                        {slot.label_vi}
                      </span>
                    </div>

                    {/* Card Middle: Status Icon & Masked/Owner Info */}
                    <div className="my-3 text-center space-y-1.5">
                      <div className="text-3xl">{style.icon}</div>
                      <div className="text-xs font-bold text-slate-800">
                        {style.subNote}
                      </div>

                      {/* Only shown if it is the current user's own booking/session */}
                      {slot.is_my_booking && slot.plate_display && (
                        <div className="inline-block font-mono text-xs font-black bg-amber-200/80 text-slate-900 px-2.5 py-1 rounded-lg border border-amber-400">
                          Xe của bạn: {slot.plate_display}
                        </div>
                      )}
                    </div>

                    {/* Card Bottom: Selection / Availability Footer */}
                    <div className="pt-2.5 border-t border-slate-200/80 flex items-center justify-between text-[11px]">
                      <span className="text-slate-500 font-medium">
                        IR: <strong>{slot.physical_status}</strong>
                      </span>
                      {slot.is_bookable && !currentBooking ? (
                        <span
                          className={`font-extrabold ${
                            isSelected ? "text-emerald-700 underline" : "text-slate-600"
                          }`}
                        >
                          {isSelected ? "✓ Đang chọn ô này" : "Bấm để chọn"}
                        </span>
                      ) : slot.is_my_booking ? (
                        <span className="font-bold text-amber-800">Đang giữ cho bạn</span>
                      ) : (
                        <span className="text-slate-400 font-semibold">Không thể đặt</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Booking Action Footer Bar */}
          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-xs text-slate-700 space-y-0.5">
              <div className="font-bold text-slate-900">
                {currentBooking
                  ? `Bạn đang có đặt chỗ hiệu lực tại ô ${currentBooking.slot_id}. Mỗi xe chỉ giữ tối đa 1 đặt chỗ hoạt động.`
                  : selectedSlotId
                  ? `Đã chọn ô ${selectedSlotId} cho xe ${
                      primaryVehicle?.plate_display || "—"
                    }. Thời hạn giữ chỗ: 60 phút tính từ giờ máy chủ.`
                  : "Hãy chọn 1 ô đỗ đang ở trạng thái 'Có thể đặt / Nhận xe' trên sơ đồ."}
              </div>
              <div className="text-[11px] text-slate-500">
                Khi xe đến cổng vào (Gate IN) trong thời gian giữ chỗ, hệ thống sẽ đối chiếu biển số và xác thực khuôn mặt tài xế 1:1.
              </div>
            </div>

            <button
              type="button"
              onClick={handleBookSlot}
              disabled={
                !!currentBooking ||
                !selectedSlotId ||
                !primaryVehicle ||
                isBookingSubmitting
              }
              className="w-full sm:w-auto bg-[#004b87] hover:bg-[#003968] disabled:bg-slate-300 disabled:text-slate-500 disabled:cursor-not-allowed text-white font-extrabold px-6 py-3 rounded-xl text-xs sm:text-sm transition cursor-pointer shadow-md whitespace-nowrap"
            >
              {isBookingSubmitting
                ? "⏳ Đang khóa giao dịch & đặt ô..."
                : selectedSlotId
                ? `🅿️ Đặt giữ ô ${selectedSlotId} (60 phút)`
                : "Chọn ô khả dụng để đặt"}
            </button>
          </div>
        </section>

        {/* Personal Booking & Parking Session History */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div>
              <h2 className="text-base font-extrabold text-[#004b87] uppercase">
                Lịch Sử Đặt Chỗ &amp; Gửi Xe Cá Nhân ({user.username})
              </h2>
              <p className="text-xs text-slate-500">
                Dữ liệu truy vấn trực tiếp từ MySQL theo tài khoản đang đăng nhập
              </p>
            </div>

            <div className="flex items-center gap-2">
              <label htmlFor="historyFilter" className="text-xs font-bold text-slate-600">
                Lọc trạng thái Booking:
              </label>
              <select
                id="historyFilter"
                value={historyStatusFilter}
                onChange={(e) => setHistoryStatusFilter(e.target.value)}
                className="text-xs font-semibold border border-slate-300 rounded-xl px-3 py-1.5 bg-white"
              >
                <option value="">Tất cả trạng thái</option>
                <option value="Reserved">Reserved (Đang giữ chỗ)</option>
                <option value="Checkin_pending">Checkin_pending (Chờ cổng vào)</option>
                <option value="Checked_in">Checked_in (Đã vào bãi)</option>
                <option value="Completed">Completed (Hoàn tất)</option>
                <option value="Expired">Expired (Hết hạn 60 phút)</option>
                <option value="Cancelled">Cancelled (Đã hủy)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Table 1: Bookings History */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2.5">
                1. Lịch sử Đặt giữ ô ({historyBookings.length})
              </h3>
              <div className="overflow-x-auto border border-slate-200 rounded-xl">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50 text-slate-600 border-b border-slate-200 font-bold">
                      <th className="py-2.5 px-3">Ô</th>
                      <th className="py-2.5 px-3">Biển số</th>
                      <th className="py-2.5 px-3">Trạng thái</th>
                      <th className="py-2.5 px-3">Thời gian đặt / Hết hạn</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {historyBookings.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-6 text-center text-slate-400">
                          Chưa có lịch sử đặt chỗ nào.
                        </td>
                      </tr>
                    ) : (
                      historyBookings.map((b) => {
                        const badge = getBookingStatusBadge(b.status);
                        return (
                          <tr key={b.booking_id} className="hover:bg-slate-50">
                            <td className="py-2.5 px-3 font-black text-sm text-[#004b87]">
                              {b.slot_id}
                            </td>
                            <td className="py-2.5 px-3 font-mono font-bold">
                              {b.plate_display || b.plate_number}
                            </td>
                            <td className="py-2.5 px-3">
                              <span
                                className={`inline-block px-2 py-0.5 rounded-md text-[11px] font-bold border ${badge.className}`}
                              >
                                {badge.label}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-[11px] text-slate-600">
                              <div>Đặt: {formatVnDateTime(b.created_at)}</div>
                              <div>Hạn: {formatVnDateTime(b.expires_at)}</div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Table 2: Parking Sessions History */}
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2.5">
                2. Lịch sử Phiên gửi xe thực tế ({historySessions.length})
              </h3>
              <div className="overflow-x-auto border border-slate-200 rounded-xl">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-slate-50 text-slate-600 border-b border-slate-200 font-bold">
                      <th className="py-2.5 px-3">Ô đỗ</th>
                      <th className="py-2.5 px-3">Biển số</th>
                      <th className="py-2.5 px-3">Trạng thái phiên</th>
                      <th className="py-2.5 px-3">Giờ vào / Giờ ra</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {historySessions.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="py-6 text-center text-slate-400">
                          Chưa có phiên gửi xe nào qua cổng.
                        </td>
                      </tr>
                    ) : (
                      historySessions.map((s) => (
                        <tr key={s.session_id} className="hover:bg-slate-50">
                          <td className="py-2.5 px-3 font-black text-sm text-[#004b87]">
                            {s.assigned_slot_id}
                          </td>
                          <td className="py-2.5 px-3 font-mono font-bold">
                            {s.plate_display || s.plate_number}
                          </td>
                          <td className="py-2.5 px-3">
                            <div className="font-bold text-slate-800">{s.status}</div>
                            <div className="text-[11px] text-slate-500">
                              {s.parking_status}
                            </div>
                          </td>
                          <td className="py-2.5 px-3 text-[11px] text-slate-600">
                            <div>Vào: {formatVnDateTime(s.entry_time)}</div>
                            <div>Ra: {formatVnDateTime(s.exit_time)}</div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* First-Person Driver Navigation Modal */}
      {currentBooking && (
        <FirstPersonDriverModal
          isOpen={isDriverModalOpen}
          onClose={() => setIsDriverModalOpen(false)}
          slotId={currentBooking.slot_id}
          plateDisplay={
            currentBooking.plate_display ||
            currentBooking.plate_number ||
            primaryVehicle?.plate_display ||
            "43A-123.45"
          }
          bookingId={currentBooking.booking_id}
        />
      )}

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-3 text-center text-xs text-slate-500 mt-auto">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span className="font-semibold text-slate-600">
            Đồ Án PBL4: Hệ Thống Bãi Đỗ Xe Thông Minh IoT (MySQL/InnoDB • Đặt Chỗ 60 Phút)
          </span>
          <span>Đại học Bách Khoa - ĐH Đà Nẵng © 2026</span>
        </div>
      </footer>
    </div>
  );
};
