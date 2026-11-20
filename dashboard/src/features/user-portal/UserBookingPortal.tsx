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
import { DRIVER_ROUTES } from "./driverRoutes";
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

function formatDurationMinutes(
  startIso: string | null | undefined,
  endIso: string | null | undefined
): string {
  if (!startIso || !endIso) return "—";
  const diffMs = Date.parse(endIso) - Date.parse(startIso);
  if (Number.isNaN(diffMs) || diffMs < 0) return "—";
  const mins = Math.max(1, Math.round(diffMs / 60000));
  if (mins < 60) return `${mins} phút`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return `${h} giờ ${m} phút`;
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
        label: "Đang đối soát cổng vào",
        className: "bg-sky-100 text-sky-900 border-sky-300",
      };
    case "Checked_in":
      return {
        label: "Đã qua cổng vào bãi",
        className: "bg-indigo-100 text-indigo-900 border-indigo-300",
      };
    case "Completed":
      return {
        label: "Hoàn tất lượt đỗ",
        className: "bg-emerald-100 text-emerald-900 border-emerald-300",
      };
    case "Expired":
      return {
        label: "Hết hạn 60 phút",
        className: "bg-rose-100 text-rose-900 border-rose-300",
      };
    case "Cancelled":
      return {
        label: "Đã hủy đặt chỗ",
        className: "bg-slate-200 text-slate-700 border-slate-300",
      };
    default:
      return {
        label: status,
        className: "bg-slate-100 text-slate-700 border-slate-300",
      };
  }
}

function getSessionStatusBadge(status: string): { label: string; className: string } {
  switch (status) {
    case "Entry_pending":
      return { label: "Chờ qua cổng vào", className: "bg-sky-100 text-sky-900 border-sky-300" };
    case "Active":
      return { label: "Đang gửi trong bãi", className: "bg-blue-100 text-blue-900 border-blue-300" };
    case "Exit_pending":
      return { label: "Đang làm thủ tục ra", className: "bg-amber-100 text-amber-900 border-amber-300" };
    case "Closed":
      return { label: "Đã rời bãi (Closed)", className: "bg-emerald-100 text-emerald-900 border-emerald-300" };
    case "Cancelled":
      return { label: "Đã hủy phiên", className: "bg-slate-200 text-slate-700 border-slate-300" };
    default:
      return { label: status, className: "bg-slate-100 text-slate-700 border-slate-300" };
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
  const [activeHistoryTab, setActiveHistoryTab] = useState<"bookings" | "sessions">("bookings");

  // Server time offset: serverTimeMs - Date.now()
  const serverOffsetMsRef = useRef<number>(0);
  // Stable per-attempt idempotency key so retries on the same slot do not double-book
  const bookingAttemptKeyRef = useRef<{ slotId: SlotId; key: string } | null>(null);

  const [lastUpdatedVn, setLastUpdatedVn] = useState<string>("—");
  const [countdownSeconds, setCountdownSeconds] = useState<number>(0);
  const [parkedElapsedSeconds, setParkedElapsedSeconds] = useState<number>(0);

  // Loading, Error, Confirmation Modal & Driver Simulation states
  const [isInitialLoading, setIsInitialLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isBookingSubmitting, setIsBookingSubmitting] = useState<boolean>(false);
  const [isCancelSubmitting, setIsCancelSubmitting] = useState<boolean>(false);
  const [isCancelConfirmOpen, setIsCancelConfirmOpen] = useState<boolean>(false);
  const [isDriverModalOpen, setIsDriverModalOpen] = useState<boolean>(false);

  const [apiErrorBanner, setApiErrorBanner] = useState<string | null>(null);
  const [feedbackBanner, setFeedbackBanner] = useState<{
    type: "success" | "warning" | "error";
    text: string;
  } | null>(null);
  const [realtimeConnected, setRealtimeConnected] = useState<boolean>(false);

  const primaryVehicle = user.vehicles[0] || null;

  const syncServerTimeOffset = (serverTimeIso?: string) => {
    if (!serverTimeIso) return;
    const parsed = Date.parse(serverTimeIso);
    if (!Number.isNaN(parsed)) {
      serverOffsetMsRef.current = parsed - Date.now();
      setLastUpdatedVn(formatVnDateTime(serverTimeIso));
    }
  };

  const refreshAllData = useCallback(
    async (manual = false) => {
      if (manual) setIsRefreshing(true);
      try {
        const [slotsRes, currentRes, historyRes] = await Promise.all([
          ParkingService.getSlots(),
          ParkingService.getCurrentBooking(),
          ParkingService.getMyHistory({
            bookingStatus: historyStatusFilter || undefined,
            limit: 50,
          }),
        ]);

        syncServerTimeOffset(slotsRes.server_time || currentRes.server_time);
        setSlots(slotsRes.slots);
        setAvailableCount(slotsRes.available_count);
        setCurrentBooking(currentRes.booking);
        setHistoryBookings(historyRes.bookings);
        setHistorySessions(historyRes.sessions);
        setApiErrorBanner(null);

        setSelectedSlotId((prev) => {
          if (
            prev &&
            slotsRes.slots.some((s) => s.slot_id === prev && s.is_bookable)
          ) {
            return prev;
          }
          const firstBookable = slotsRes.slots.find((s) => s.is_bookable);
          return firstBookable ? firstBookable.slot_id : null;
        });
      } catch (err) {
        if (err instanceof ApiError) {
          setApiErrorBanner(`[${err.reasonCode}] ${err.message}`);
        } else {
          setApiErrorBanner(
            "Mất kết nối tới máy chủ FastAPI. Không thể tải dữ liệu trạng thái ô đỗ thực tế."
          );
        }
      } finally {
        setIsInitialLoading(false);
        if (manual) setIsRefreshing(false);
      }
    },
    [historyStatusFilter]
  );

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

  // Accurate 1-second server-synchronized countdown timer (persists accurately across F5 reload)
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
        refreshAllData();
      }
    };

    computeRemaining();
    const timer = window.setInterval(computeRemaining, 1000);
    return () => window.clearInterval(timer);
  }, [currentBooking, refreshAllData]);

  // Live elapsed timer once the car has entered the parking lot (status === 'Checked_in' & entry_time set)
  useEffect(() => {
    if (
      !currentBooking ||
      currentBooking.status !== "Checked_in" ||
      !currentBooking.entry_time
    ) {
      setParkedElapsedSeconds(0);
      return;
    }

    const entryMs = Date.parse(currentBooking.entry_time);
    if (Number.isNaN(entryMs)) {
      setParkedElapsedSeconds(0);
      return;
    }

    const updateElapsed = () => {
      const nowServerMs = Date.now() + serverOffsetMsRef.current;
      setParkedElapsedSeconds(Math.max(0, Math.floor((nowServerMs - entryMs) / 1000)));
    };
    updateElapsed();
    const timer = window.setInterval(updateElapsed, 1000);
    return () => window.clearInterval(timer);
  }, [currentBooking]);

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

    // Reuse stable idempotency key for same slot retry attempt
    if (
      !bookingAttemptKeyRef.current ||
      bookingAttemptKeyRef.current.slotId !== selectedSlotId
    ) {
      bookingAttemptKeyRef.current = {
        slotId: selectedSlotId,
        key: `book-${user.user_id}-${primaryVehicle.vehicle_id}-${selectedSlotId}-${Date.now()}`,
      };
    }
    const idempotencyKey = bookingAttemptKeyRef.current.key;

    try {
      const created = await ParkingService.createBooking(
        primaryVehicle.vehicle_id,
        selectedSlotId,
        idempotencyKey
      );
      bookingAttemptKeyRef.current = null;
      syncServerTimeOffset(created.server_time);
      setCurrentBooking(created);
      setFeedbackBanner({
        type: "success",
        text: `Đặt giữ ô ${created.slot_id} thành công trong 60 phút cho xe ${
          created.plate_display || created.plate_number
        }! Nhấn "Xem đường đi" bất cứ lúc nào để xem lại mô phỏng góc nhìn sau vô lăng.`,
      });
      await refreshAllData();
      setIsDriverModalOpen(true);
    } catch (err) {
      if (err instanceof ApiError) {
        // Clear attempt key on deterministic conflict/4xx so user can pick another slot cleanly
        if (err.status >= 400 && err.status < 500) {
          bookingAttemptKeyRef.current = null;
        }
        if (err.status === 409) {
          setFeedbackBanner({
            type: "warning",
            text: `Xung đột đặt chỗ (HTTP 409 • ${err.reasonCode}): ${err.message}`,
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
          text: "Lỗi kết nối mạng khi đặt chỗ. Bạn có thể bấm lại để thử an toàn (đã bảo vệ chống đặt trùng).",
        });
      }
      await refreshAllData();
    } finally {
      setIsBookingSubmitting(false);
    }
  };

  const handleConfirmCancelBooking = async () => {
    if (!currentBooking || isCancelSubmitting) return;
    setIsCancelSubmitting(true);
    setFeedbackBanner(null);
    try {
      const cancelled = await ParkingService.cancelBooking(
        currentBooking.booking_id
      );
      setIsCancelConfirmOpen(false);
      syncServerTimeOffset(cancelled.server_time);
      setFeedbackBanner({
        type: "warning",
        text: `Đã hủy đặt giữ ô ${cancelled.slot_id} thành công. Ô đỗ đã được mở lại cho hệ thống.`,
      });
      await refreshAllData();
    } catch (err) {
      setIsCancelConfirmOpen(false);
      if (err instanceof ApiError) {
        setFeedbackBanner({
          type: "error",
          text: `Không thể hủy đặt chỗ (${err.reasonCode}): ${err.message}`,
        });
      } else {
        setFeedbackBanner({
          type: "error",
          text: "Lỗi kết nối mạng khi hủy đặt chỗ.",
        });
      }
      await refreshAllData();
    } finally {
      setIsCancelSubmitting(false);
    }
  };

  const getSlotById = (id: SlotId): ParkingSlotView | undefined =>
    slots.find((s) => s.slot_id === id);

  const getSlotVisualStyle = (
    displayStatus: DisplaySlotStatus,
    isSelected: boolean,
    isMyBooking: boolean,
    isMySession: boolean
  ) => {
    switch (displayStatus) {
      case "AVAILABLE":
        return {
          cardClass: isSelected
            ? "border-emerald-600 ring-4 ring-emerald-200 bg-emerald-50 shadow-md scale-[1.01]"
            : "border-emerald-400 bg-white hover:border-emerald-600 hover:bg-emerald-50/60",
          badgeClass: "bg-emerald-600 text-white",
          icon: "🟢",
          hint: isSelected ? "✓ Đang chọn đặt ô này" : "Bấm chọn để đặt 60 phút",
        };
      case "RESERVED":
        return {
          cardClass: isMyBooking
            ? "border-amber-500 ring-2 ring-amber-200 bg-amber-50 shadow-sm"
            : "border-amber-300 bg-amber-50/40 opacity-90",
          badgeClass: "bg-amber-500 text-slate-950",
          icon: "⏳",
          hint: isMyBooking ? "Ô bạn đang đặt giữ" : "Đã có người đặt trước",
        };
      case "ASSIGNED_PENDING":
        return {
          cardClass: isMySession
            ? "border-sky-500 ring-2 ring-sky-200 bg-sky-50 shadow-sm"
            : "border-sky-400 bg-sky-50/50 opacity-90",
          badgeClass: "bg-sky-600 text-white",
          icon: "🚗",
          hint: isMySession
            ? "Đang chờ xe của bạn tiến vào ô"
            : "Đang cấp cho xe qua cổng",
        };
      case "OCCUPIED":
        return {
          cardClass: isMySession
            ? "border-[#004b87] ring-2 ring-blue-300 bg-blue-50 shadow-sm"
            : "border-[#004b87] bg-blue-50/50 opacity-90",
          badgeClass: "bg-[#004b87] text-white",
          icon: "🚙",
          hint: isMySession
            ? "✓ Xe của bạn đang đỗ trong ô này"
            : "Đang có xe đỗ trong ô",
        };
      case "UNKNOWN_OR_FAULT":
      default:
        return {
          cardClass: "border-rose-400 bg-rose-50/60 opacity-90",
          badgeClass: "bg-rose-600 text-white",
          icon: "⚠️",
          hint: "Cảm biến quá hạn / Lỗi dữ liệu",
        };
    }
  };

  const highlightedSlotId: SlotId | null =
    currentBooking?.slot_id || selectedSlotId || null;

  const renderFloorPlanSlotCard = (slotId: SlotId) => {
    const slot = getSlotById(slotId);
    if (!slot) {
      return (
        <div
          key={slotId}
          className="border-2 border-dashed border-rose-300 bg-rose-50/40 rounded-2xl p-4 min-h-[155px] flex flex-col items-center justify-center text-xs text-rose-700 font-bold"
        >
          <span>⚠️ Ô {slotId}</span>
          <span className="text-[11px] font-medium mt-1">
            Chưa đủ dữ liệu cảm biến
          </span>
        </div>
      );
    }

    const isSelected = !currentBooking && selectedSlotId === slot.slot_id;
    const style = getSlotVisualStyle(
      slot.display_status,
      isSelected,
      slot.is_my_booking,
      slot.is_my_session
    );
    const canSelect = slot.is_bookable && !currentBooking;
    const isMine = slot.is_my_booking || slot.is_my_session;

    return (
      <button
        key={slot.slot_id}
        type="button"
        disabled={!canSelect && !isMine}
        onClick={() => {
          if (canSelect) {
            setSelectedSlotId(slot.slot_id);
          }
        }}
        className={`w-full text-left border-2 rounded-2xl p-3.5 sm:p-4 flex flex-col justify-between min-h-[164px] transition-all ${
          style.cardClass
        } ${canSelect ? "cursor-pointer" : "cursor-default"}`}
      >
        {/* Top Row: Slot ID + Status Badge */}
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-black text-slate-900 leading-none">
                {slot.slot_id}
              </span>
              <span className="text-lg">{style.icon}</span>
            </div>
            <div className="text-[11px] text-slate-500 font-mono mt-1">
              {slot.sensor_id} • IR: {slot.physical_status}
            </div>
          </div>
          <span
            className={`text-[11px] font-extrabold px-2.5 py-1 rounded-lg shadow-2xs text-right leading-tight ${style.badgeClass}`}
          >
            {slot.label_vi}
          </span>
        </div>

        {/* Middle Info: Own Vehicle Plate or Route Summary */}
        <div className="my-2.5">
          {isMine && slot.plate_display ? (
            <div
              className={`inline-flex items-center gap-1.5 font-mono text-xs font-black px-2.5 py-1 rounded-lg border ${
                slot.is_my_session
                  ? "bg-blue-100 text-blue-950 border-blue-400"
                  : "bg-amber-200/90 text-slate-950 border-amber-400"
              }`}
            >
              <span>{slot.is_my_session ? "🚙" : "🚘"}</span>
              <span>
                {slot.is_my_session ? "Đang đỗ:" : "Xe của bạn:"} {slot.plate_display}
              </span>
            </div>
          ) : isSelected ? (
            <div className="text-[11px] font-bold text-emerald-800 bg-emerald-100/90 px-2.5 py-1 rounded-lg border border-emerald-300">
              {DRIVER_ROUTES[slot.slot_id].turnLabelVi}
            </div>
          ) : (
            <div className="text-[11px] text-slate-500 font-medium">
              {DRIVER_ROUTES[slot.slot_id].zoneLabel}
            </div>
          )}
        </div>

        {/* Bottom Hint */}
        <div className="pt-2 border-t border-slate-200/70 flex items-center justify-between text-[11px]">
          <span className="font-bold text-slate-700">{style.hint}</span>
          {canSelect && (
            <span
              className={`text-[11px] font-extrabold ${
                isSelected ? "text-emerald-700" : "text-[#004b87]"
              }`}
            >
              {isSelected ? "Đã chọn" : "Chọn →"}
            </span>
          )}
        </div>
      </button>
    );
  };

  // Countdown urgency styling
  const countdownPct = Math.min(100, Math.max(0, (countdownSeconds / 3600) * 100));
  const countdownColorClass =
    countdownSeconds <= 300
      ? "text-rose-400 border-rose-500/70"
      : countdownSeconds <= 900
      ? "text-amber-300 border-amber-400/70"
      : "text-emerald-300 border-emerald-400/60";
  const countdownBarClass =
    countdownSeconds <= 300
      ? "bg-rose-500"
      : countdownSeconds <= 900
      ? "bg-amber-400"
      : "bg-emerald-400";

  const bookingStepIndex = !currentBooking
    ? -1
    : currentBooking.status === "Reserved"
    ? 0
    : currentBooking.status === "Checkin_pending"
    ? 1
    : currentBooking.status === "Checked_in"
    ? 2
    : 3;

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 text-slate-800">
      {/* Top Institutional & Driver Identity Header */}
      <header className="bg-gradient-to-r from-[#002f57] via-[#004b87] to-[#003366] text-white shadow-lg sticky top-0 z-30 border-b border-blue-950">
        <div className="max-w-6xl mx-auto px-4 py-3 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-amber-400 text-slate-950 font-black flex flex-col items-center justify-center shadow-md flex-shrink-0">
              <span className="text-sm leading-none">PBL4</span>
              <span className="text-[8px] font-bold mt-0.5">USER</span>
            </div>
            <div>
              <div className="text-[11px] text-amber-300 font-bold uppercase tracking-wider">
                Hệ Thống Bãi Đỗ Xe Thông Minh IoT • Cổng Người Dùng
              </div>
              <h1 className="text-base sm:text-lg font-extrabold tracking-tight">
                Đặt Giữ Ô Đỗ 60 Phút &amp; Dẫn Đường Góc Nhìn Người Lái
              </h1>
            </div>
          </div>

          {/* Registered Driver, Vehicle & Encrypted Face Template Badges */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="bg-white/10 backdrop-blur-xs border border-white/15 rounded-xl px-3 py-1.5 text-xs">
              <div className="text-[10px] text-blue-200 uppercase font-bold">
                Chủ xe ({user.username})
              </div>
              <div className="font-bold text-white">{user.display_name}</div>
            </div>

            <div className="bg-white/10 backdrop-blur-xs border border-white/15 rounded-xl px-3 py-1.5 text-xs">
              <div className="text-[10px] text-blue-200 uppercase font-bold">
                Xe định danh có sẵn
              </div>
              <div className="font-mono font-black text-amber-300">
                {primaryVehicle
                  ? `${primaryVehicle.plate_display} (${primaryVehicle.plate_number})`
                  : "Chưa gán xe"}
              </div>
            </div>

            <div className="bg-white/10 backdrop-blur-xs border border-white/15 rounded-xl px-3 py-1.5 text-xs">
              <div className="text-[10px] text-blue-200 uppercase font-bold">
                Mẫu khuôn mặt 512-D
              </div>
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
              type="button"
              onClick={onLogout}
              className="bg-rose-600 hover:bg-rose-500 text-white font-bold px-3.5 py-2.5 rounded-xl text-xs transition cursor-pointer shadow"
            >
              Đăng xuất
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 flex-1 w-full space-y-6">
        {/* API / Network Error Banner (Never hides errors or fabricates Free slots!) */}
        {apiErrorBanner && (
          <div
            role="alert"
            className="bg-rose-50 border-2 border-rose-500 text-rose-950 rounded-2xl p-4 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3"
          >
            <div>
              <div className="font-extrabold text-sm">
                🚨 LỖI KẾT NỐI MÁY CHỦ / CẢM BIẾN
              </div>
              <p className="text-xs font-medium mt-1">{apiErrorBanner}</p>
            </div>
            <button
              type="button"
              onClick={() => refreshAllData(true)}
              className="bg-rose-700 hover:bg-rose-600 text-white font-bold px-4 py-2 rounded-xl text-xs transition cursor-pointer self-start sm:self-center"
            >
              🔄 Thử kết nối lại
            </button>
          </div>
        )}

        {/* Action Feedback Banner (Success / 409 Conflict / Cancel) */}
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
              type="button"
              onClick={() => setFeedbackBanner(null)}
              className="text-slate-600 hover:text-slate-950 font-bold px-2 py-1 cursor-pointer"
            >
              ✕
            </button>
          </div>
        )}

        {/* Active Booking / Active Parked Session Command Panel */}
        {currentBooking && (
          <section
            className={`text-white rounded-2xl p-5 shadow-xl border-2 space-y-4 ${
              currentBooking.status === "Checked_in" &&
              currentBooking.parking_status === "Parked_confirmed"
                ? "bg-gradient-to-br from-emerald-950 via-[#003c5f] to-[#004b87] border-emerald-400"
                : "bg-gradient-to-br from-slate-900 via-[#003366] to-[#004b87] border-amber-400/90"
            }`}
          >
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 flex-wrap">
                  {currentBooking.status === "Reserved" && (
                    <span className="bg-amber-400 text-slate-950 text-[11px] font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                      Đặt Chỗ Đang Hiệu Lực (Chờ xe đến cổng)
                    </span>
                  )}
                  {currentBooking.status === "Checkin_pending" && (
                    <span className="bg-sky-400 text-slate-950 text-[11px] font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider animate-pulse">
                      Đang Đối Soát Biển Số &amp; Khuôn Mặt Tại Cổng Vào
                    </span>
                  )}
                  {currentBooking.status === "Checked_in" &&
                    currentBooking.parking_status === "Parked_confirmed" && (
                      <span className="bg-emerald-400 text-slate-950 text-[11px] font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                        ✓ Xe Đã Đỗ Ổn Định Trong Ô {currentBooking.slot_id}
                      </span>
                    )}
                  {currentBooking.status === "Checked_in" &&
                    currentBooking.parking_status === "Parking_pending" && (
                      <span className="bg-sky-400 text-slate-950 text-[11px] font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                        🚗 Đã Qua Cổng Vào • Đang Di Chuyển Vào Ô {currentBooking.slot_id}
                      </span>
                    )}
                  {currentBooking.status === "Checked_in" &&
                    (currentBooking.parking_status === "Parking_review_required" ||
                      currentBooking.parking_status === "Parking_timeout") && (
                      <span className="bg-rose-500 text-white text-[11px] font-black px-2.5 py-0.5 rounded-full uppercase tracking-wider">
                        ⚠️ Cần Kiểm Tra Vị Trí Đỗ ({currentBooking.parking_status})
                      </span>
                    )}
                  <span className="text-xs font-mono text-blue-200">
                    #{currentBooking.booking_id.slice(0, 8)}
                  </span>
                </div>
                <h2 className="text-xl sm:text-2xl font-black flex items-center gap-3 flex-wrap">
                  <span>
                    {currentBooking.status === "Checked_in"
                      ? `Đang Đỗ Tại Ô: ${currentBooking.slot_id}`
                      : `Ô Đã Đặt: ${currentBooking.slot_id}`}
                  </span>
                  <span className="text-sm font-mono bg-white/15 px-3 py-1 rounded-xl border border-white/20 text-amber-300">
                    {currentBooking.plate_display || currentBooking.plate_number}
                  </span>
                </h2>
                <div className="text-xs text-blue-100 flex flex-wrap gap-x-5 gap-y-1">
                  <span>
                    Vị trí:{" "}
                    <strong className="text-white">
                      {DRIVER_ROUTES[currentBooking.slot_id].zoneLabel}
                    </strong>
                  </span>
                  {currentBooking.status === "Checked_in" && currentBooking.entry_time ? (
                    <>
                      <span>
                        Giờ qua cổng vào:{" "}
                        <strong className="text-emerald-300">
                          {formatVnDateTime(currentBooking.entry_time)}
                        </strong>
                      </span>
                      <span>
                        Trạng thái cảm biến đỗ:{" "}
                        <strong className="text-white">
                          {currentBooking.parking_status === "Parked_confirmed"
                            ? "Đã xác nhận đỗ đúng ô"
                            : currentBooking.parking_status}
                        </strong>
                      </span>
                    </>
                  ) : (
                    <>
                      <span>
                        Giờ đặt:{" "}
                        <strong>{formatVnDateTime(currentBooking.created_at)}</strong>
                      </span>
                      <span>
                        Hết hạn:{" "}
                        <strong className="text-amber-300">
                          {formatVnDateTime(currentBooking.expires_at)}
                        </strong>
                      </span>
                    </>
                  )}
                </div>
              </div>

              {/* Countdown Timer (Reserved) OR Live Parked Elapsed Timer (Checked_in) + Actions */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                {currentBooking.status === "Reserved" && (
                  <div
                    className={`bg-slate-950/90 border-2 rounded-2xl px-4 py-2.5 min-w-[165px] text-center ${countdownColorClass}`}
                  >
                    <div className="text-[10px] uppercase tracking-wider text-slate-300 font-bold">
                      Giữ ô còn lại (Server)
                    </div>
                    <div
                      data-testid="booking-countdown"
                      className="text-3xl font-black font-mono tracking-wider leading-tight mt-0.5"
                    >
                      {formatCountdownMMSS(countdownSeconds)}
                    </div>
                    <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden mt-1.5">
                      <div
                        className={`h-full transition-all duration-500 ${countdownBarClass}`}
                        style={{ width: `${countdownPct}%` }}
                      />
                    </div>
                  </div>
                )}

                {currentBooking.status === "Checked_in" && (
                  <div className="bg-slate-950/90 border-2 border-emerald-400/70 rounded-2xl px-4 py-2.5 min-w-[165px] text-center text-emerald-300">
                    <div className="text-[10px] uppercase tracking-wider text-slate-300 font-bold">
                      Thời gian đang gửi xe
                    </div>
                    <div className="text-3xl font-black font-mono tracking-wider leading-tight mt-0.5">
                      {formatCountdownMMSS(parkedElapsedSeconds)}
                    </div>
                    <div className="text-[10px] font-bold text-emerald-400 mt-1">
                      {currentBooking.parking_status === "Parked_confirmed"
                        ? "● Đã đỗ ổn định"
                        : "● Đang di chuyển vào ô"}
                    </div>
                  </div>
                )}

                <div className="flex flex-col sm:flex-row gap-2">
                  <button
                    type="button"
                    onClick={() => setIsDriverModalOpen(true)}
                    className="bg-amber-400 hover:bg-amber-300 text-slate-950 font-extrabold px-4 py-3 rounded-xl text-xs transition cursor-pointer shadow-lg flex items-center justify-center gap-1.5"
                  >
                    <span>🚘</span>
                    <span>Xem đường đi (Góc nhìn người lái)</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setIsCancelConfirmOpen(true)}
                    disabled={!currentBooking.can_cancel || isCancelSubmitting}
                    title={
                      currentBooking.can_cancel
                        ? "Hủy giữ chỗ ô đỗ này"
                        : "Không thể hủy khi xe đã bắt đầu đối soát tại cổng vào"
                    }
                    className="bg-rose-600 hover:bg-rose-500 disabled:bg-slate-600 disabled:text-slate-300 disabled:cursor-not-allowed text-white font-bold px-4 py-3 rounded-xl text-xs transition cursor-pointer shadow"
                  >
                    ✕ Hủy đặt chỗ
                  </button>
                </div>
              </div>
            </div>

            {/* 4-Step Booking Lifecycle Stepper */}
            <div className="pt-3 border-t border-white/15 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
              {[
                { idx: 0, label: "1. Đã giữ chỗ 60 phút" },
                { idx: 1, label: "2. Đối soát cổng vào" },
                { idx: 2, label: "3. Đã vào bãi đỗ" },
                { idx: 3, label: "4. Rời bãi hoàn tất" },
              ].map((step) => {
                const isDone = bookingStepIndex > step.idx;
                const isCurrent = bookingStepIndex === step.idx;
                return (
                  <div
                    key={step.idx}
                    className={`rounded-xl px-3 py-1.5 font-bold flex items-center gap-1.5 border ${
                      isCurrent
                        ? "bg-amber-400/20 border-amber-400 text-amber-200"
                        : isDone
                        ? "bg-emerald-500/20 border-emerald-400/60 text-emerald-200"
                        : "bg-slate-950/40 border-white/10 text-slate-400"
                    }`}
                  >
                    <span>{isDone ? "✓" : isCurrent ? "●" : "○"}</span>
                    <span>{step.label}</span>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* Interactive 2D Parking Lot Floor Plan (A1, A2, B1, B2) */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-slate-100">
            <div>
              <h2 className="text-base sm:text-lg font-extrabold text-[#004b87] uppercase">
                Sơ Đồ Mặt Bằng Bãi Đỗ Xe (4 Ô: A1, A2, B1, B2)
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Chọn trực tiếp 1 ô đang ở trạng thái{" "}
                <strong className="text-emerald-700">Có thể đặt / Nhận xe</strong>{" "}
                trên mặt bằng để giữ chỗ 60 phút theo giờ máy chủ.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs">
              <div className="bg-emerald-50 border border-emerald-200 px-3 py-1.5 rounded-xl font-bold text-emerald-900">
                Khả dụng:{" "}
                <span className="text-base font-black text-emerald-700">
                  {availableCount}
                </span>{" "}
                / 4 ô
              </div>
              <div className="bg-slate-100 border border-slate-200 px-3 py-1.5 rounded-xl text-slate-600 font-medium">
                Cập nhật: <strong>{lastUpdatedVn}</strong>
              </div>
              <button
                type="button"
                onClick={() => refreshAllData(true)}
                disabled={isRefreshing}
                className="bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold px-3 py-1.5 rounded-xl border border-slate-300 transition cursor-pointer"
              >
                {isRefreshing ? "⏳ Đang tải..." : "🔄 Làm mới"}
              </button>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-slate-900 text-white text-[11px] font-bold">
                <span
                  className={`w-2 h-2 rounded-full ${
                    realtimeConnected
                      ? "bg-emerald-400 animate-pulse"
                      : "bg-amber-400"
                  }`}
                />
                {realtimeConnected ? "Realtime Live" : "Đồng bộ định kỳ"}
              </span>
            </div>
          </div>

          {/* Color & Vietnamese Label Legend */}
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-bold">
            <span className="px-2.5 py-1 rounded-lg bg-emerald-100 text-emerald-900 border border-emerald-300">
              🟢 Có thể đặt / Nhận xe
            </span>
            <span className="px-2.5 py-1 rounded-lg bg-amber-100 text-amber-900 border border-amber-300">
              ⏳ Đã đặt trước
            </span>
            <span className="px-2.5 py-1 rounded-lg bg-sky-100 text-sky-900 border border-sky-300">
              🚗 Đang cấp / Chờ xe đỗ
            </span>
            <span className="px-2.5 py-1 rounded-lg bg-blue-100 text-blue-900 border border-blue-300">
              🚙 Đang có xe
            </span>
            <span className="px-2.5 py-1 rounded-lg bg-rose-100 text-rose-900 border border-rose-300">
              ⚠️ Chưa đủ dữ liệu / Lỗi cảm biến
            </span>
          </div>

          {/* Spatial Floor Plan Container */}
          {isInitialLoading ? (
            <div className="py-14 text-center text-sm font-semibold text-slate-500">
              ⏳ Đang tải trạng thái thực tế của 4 ô đỗ từ MySQL...
            </div>
          ) : slots.length === 0 ? (
            <div className="py-10 text-center bg-rose-50 border border-rose-200 rounded-xl text-xs font-bold text-rose-800">
              ⚠️ Chưa đủ dữ liệu / Lỗi kết nối: Không nhận được dữ liệu 4 ô đỗ từ máy chủ.
            </div>
          ) : (
            <div className="bg-slate-900/5 border-2 border-slate-200 rounded-2xl p-4 sm:p-5 space-y-4">
              {/* Top Gate OUT Marker */}
              <div className="flex justify-center">
                <div className="bg-slate-800 text-slate-200 px-4 py-1 rounded-full text-[11px] font-extrabold uppercase tracking-wider shadow-xs">
                  ▲ Lối Ra Xe (Gate OUT • Đối chiếu Khuôn Mặt Phiên 1:1)
                </div>
              </div>

              {/* Row B: B1 (Left) — Central Driving Aisle — B2 (Right) */}
              <div className="grid grid-cols-1 md:grid-cols-11 gap-3 items-stretch">
                <div className="md:col-span-5">{renderFloorPlanSlotCard("B1")}</div>

                {/* Central Lane Row B */}
                <div className="hidden md:flex md:col-span-1 flex-col items-center justify-center bg-slate-800 rounded-xl relative overflow-hidden border border-slate-700">
                  <div className="h-full border-l-2 border-dashed border-slate-500/70 absolute left-1/2" />
                  <span
                    className={`z-10 text-sm font-black px-1.5 py-1 rounded ${
                      highlightedSlotId === "B1"
                        ? "bg-sky-400 text-slate-950"
                        : highlightedSlotId === "B2"
                        ? "bg-sky-400 text-slate-950"
                        : "bg-slate-700 text-slate-300"
                    }`}
                  >
                    {highlightedSlotId === "B1"
                      ? "↰"
                      : highlightedSlotId === "B2"
                      ? "↱"
                      : "↑"}
                  </span>
                  <span className="z-10 text-[9px] font-bold text-slate-300 mt-1">
                    Dãy B
                  </span>
                </div>

                <div className="md:col-span-5">{renderFloorPlanSlotCard("B2")}</div>
              </div>

              {/* Row A: A1 (Left) — Central Driving Aisle — A2 (Right) */}
              <div className="grid grid-cols-1 md:grid-cols-11 gap-3 items-stretch">
                <div className="md:col-span-5">{renderFloorPlanSlotCard("A1")}</div>

                {/* Central Lane Row A */}
                <div className="hidden md:flex md:col-span-1 flex-col items-center justify-center bg-slate-800 rounded-xl relative overflow-hidden border border-slate-700">
                  <div className="h-full border-l-2 border-dashed border-slate-500/70 absolute left-1/2" />
                  <span
                    className={`z-10 text-sm font-black px-1.5 py-1 rounded ${
                      highlightedSlotId === "A1" ||
                      highlightedSlotId === "A2" ||
                      highlightedSlotId === "B1" ||
                      highlightedSlotId === "B2"
                        ? "bg-sky-400 text-slate-950"
                        : "bg-slate-700 text-slate-300"
                    }`}
                  >
                    {highlightedSlotId === "A1"
                      ? "↰"
                      : highlightedSlotId === "A2"
                      ? "↱"
                      : "↑"}
                  </span>
                  <span className="z-10 text-[9px] font-bold text-slate-300 mt-1">
                    Dãy A
                  </span>
                </div>

                <div className="md:col-span-5">{renderFloorPlanSlotCard("A2")}</div>
              </div>

              {/* Bottom Gate IN Marker */}
              <div className="flex justify-center">
                <div className="bg-amber-400 text-slate-950 px-5 py-1.5 rounded-full text-xs font-black uppercase tracking-wider shadow-sm border border-amber-500">
                  🚧 Cổng Vào (Gate IN • Barie Tự Động &amp; Quét Biển Số / Khuôn Mặt)
                </div>
              </div>
            </div>
          )}

          {/* Primary Booking Submission Bar */}
          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="text-xs text-slate-700 space-y-1">
              <div className="font-bold text-slate-900">
                {currentBooking
                  ? `Bạn đang giữ ô ${currentBooking.slot_id}. Mỗi phương tiện chỉ giữ tối đa 1 đặt chỗ hoạt động tại một thời điểm.`
                  : selectedSlotId
                  ? `Sẵn sàng đặt giữ ô ${selectedSlotId} (${
                      DRIVER_ROUTES[selectedSlotId].zoneLabel
                    }) cho xe ${primaryVehicle?.plate_display || "—"} trong 60 phút.`
                  : "Hãy chọn 1 ô đang ở trạng thái 'Có thể đặt / Nhận xe' trên sơ đồ mặt bằng."}
              </div>
              <div className="text-[11px] text-slate-500">
                Hệ thống khóa dòng nguyên tử trên MySQL chống đặt trùng đồng thời và tự động đồng bộ thời gian hết hạn từ máy chủ.
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
                ? "⏳ Đang xử lý giao dịch đặt ô..."
                : selectedSlotId
                ? `🅿️ Đặt giữ ô ${selectedSlotId} (60 phút)`
                : "Chọn ô khả dụng để đặt"}
            </button>
          </div>
        </section>

        {/* Tabbed Personal History Section */}
        <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                onClick={() => setActiveHistoryTab("bookings")}
                className={`px-4 py-2 rounded-xl text-xs font-extrabold transition cursor-pointer ${
                  activeHistoryTab === "bookings"
                    ? "bg-[#004b87] text-white shadow-xs"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                📅 Lịch sử Đặt giữ ô ({historyBookings.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveHistoryTab("sessions")}
                className={`px-4 py-2 rounded-xl text-xs font-extrabold transition cursor-pointer ${
                  activeHistoryTab === "sessions"
                    ? "bg-[#004b87] text-white shadow-xs"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                🚗 Lịch sử Phiên gửi xe ({historySessions.length})
              </button>
            </div>

            {activeHistoryTab === "bookings" && (
              <div className="flex items-center gap-2">
                <label
                  htmlFor="historyFilter"
                  className="text-xs font-bold text-slate-600"
                >
                  Lọc trạng thái:
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
            )}
          </div>

          {activeHistoryTab === "bookings" ? (
            <div className="overflow-x-auto border border-slate-200 rounded-xl">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 text-slate-600 border-b border-slate-200 font-bold">
                    <th className="py-2.5 px-3">Ô đỗ</th>
                    <th className="py-2.5 px-3">Biển số xe</th>
                    <th className="py-2.5 px-3">Trạng thái</th>
                    <th className="py-2.5 px-3">Giờ đặt</th>
                    <th className="py-2.5 px-3">Hết hạn / Kết thúc</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {historyBookings.length === 0 ? (
                    <tr>
                      <td
                        colSpan={5}
                        className="py-8 text-center text-slate-400 font-medium"
                      >
                        Chưa có bản ghi đặt chỗ nào phù hợp bộ lọc.
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
                              className={`inline-block px-2.5 py-0.5 rounded-lg text-[11px] font-bold border ${badge.className}`}
                            >
                              {badge.label}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-600">
                            {formatVnDateTime(b.created_at)}
                          </td>
                          <td className="py-2.5 px-3 text-slate-600">
                            {b.cancelled_at
                              ? `Hủy: ${formatVnDateTime(b.cancelled_at)}`
                              : b.completed_at
                              ? `Xong: ${formatVnDateTime(b.completed_at)}`
                              : formatVnDateTime(b.expires_at)}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="overflow-x-auto border border-slate-200 rounded-xl">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 text-slate-600 border-b border-slate-200 font-bold">
                    <th className="py-2.5 px-3">Ô được cấp</th>
                    <th className="py-2.5 px-3">Biển số xe</th>
                    <th className="py-2.5 px-3">Trạng thái phiên</th>
                    <th className="py-2.5 px-3">Vị trí đỗ</th>
                    <th className="py-2.5 px-3">Giờ vào / Giờ ra</th>
                    <th className="py-2.5 px-3">Thời lượng</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {historySessions.length === 0 ? (
                    <tr>
                      <td
                        colSpan={6}
                        className="py-8 text-center text-slate-400 font-medium"
                      >
                        Chưa có phiên gửi xe nào qua cổng thực tế.
                      </td>
                    </tr>
                  ) : (
                    historySessions.map((s) => {
                      const sBadge = getSessionStatusBadge(s.status);
                      return (
                        <tr key={s.session_id} className="hover:bg-slate-50">
                          <td className="py-2.5 px-3 font-black text-sm text-[#004b87]">
                            {s.assigned_slot_id}
                          </td>
                          <td className="py-2.5 px-3 font-mono font-bold">
                            {s.plate_display || s.plate_number}
                          </td>
                          <td className="py-2.5 px-3">
                            <span
                              className={`inline-block px-2.5 py-0.5 rounded-lg text-[11px] font-bold border ${sBadge.className}`}
                            >
                              {sBadge.label}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 font-semibold text-slate-700">
                            {s.parking_status}
                          </td>
                          <td className="py-2.5 px-3 text-[11px] text-slate-600">
                            <div>Vào: {formatVnDateTime(s.entry_time)}</div>
                            <div>Ra: {formatVnDateTime(s.exit_time)}</div>
                          </td>
                          <td className="py-2.5 px-3 font-bold text-slate-700">
                            {formatDurationMinutes(s.entry_time, s.exit_time)}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>

      {/* In-App Confirmation Modal for Cancelling Booking */}
      {isCancelConfirmOpen && currentBooking && (
        <div
          className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-xs flex items-center justify-center p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-white rounded-2xl max-w-md w-full p-5 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-100 text-rose-700 flex items-center justify-center text-lg font-black flex-shrink-0">
                ⚠️
              </div>
              <div>
                <h3 className="text-base font-extrabold text-slate-900">
                  Xác nhận hủy đặt chỗ ô {currentBooking.slot_id}?
                </h3>
                <p className="text-xs text-slate-600 mt-1">
                  Ô <strong>{currentBooking.slot_id}</strong> cho xe{" "}
                  <strong className="font-mono">
                    {currentBooking.plate_display || currentBooking.plate_number}
                  </strong>{" "}
                  sẽ được trả về trạng thái trống ngay lập tức. Lịch sử đặt chỗ vẫn được lưu lại trong hệ thống.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                disabled={isCancelSubmitting}
                onClick={() => setIsCancelConfirmOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-bold bg-slate-100 hover:bg-slate-200 text-slate-700 cursor-pointer"
              >
                Quay lại
              </button>
              <button
                type="button"
                disabled={isCancelSubmitting}
                onClick={handleConfirmCancelBooking}
                className="px-4 py-2 rounded-xl text-xs font-extrabold bg-rose-600 hover:bg-rose-500 disabled:bg-rose-300 text-white cursor-pointer shadow"
              >
                {isCancelSubmitting ? "⏳ Đang hủy..." : "Xác nhận hủy chỗ"}
              </button>
            </div>
          </div>
        </div>
      )}

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

      <footer className="bg-white border-t border-slate-200 py-3 text-center text-xs text-slate-500 mt-auto">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span className="font-semibold text-slate-600">
            Đồ Án PBL4: Bãi Đỗ Xe Thông Minh IoT (MySQL/InnoDB • Đặt Chỗ 60 Phút)
          </span>
          <span>Đại học Bách Khoa - ĐH Đà Nẵng © 2026</span>
        </div>
      </footer>
    </div>
  );
};
