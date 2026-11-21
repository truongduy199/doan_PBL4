import React, { useCallback, useEffect, useRef, useState } from "react";
import { ApiClient, ApiError } from "../../services/api.client";
import { ParkingService } from "../../services/parking.service";
import {
  BookingDTO,
  ParkingSlotView,
  SessionDTO,
  SlotId,
  UserProfile,
} from "../../shared/types";
import { AppShell, Notice, StatusBadge, ParkingFloorPlan, EmptyState, ConfirmDialog, statusLabel } from "../../shared/components/ui";
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
  const expiryRefreshRef = useRef<string | null>(null);

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
          setApiErrorBanner(err.message);
        } else {
          setApiErrorBanner(
            "Không thể kết nối máy chủ để cập nhật chỗ đỗ."
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
    const poll = window.setInterval(() => refreshAllData(), 10000);
    return () => window.clearInterval(poll);
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
      if (diffSec === 0 && expiryRefreshRef.current !== currentBooking.booking_id) {
        expiryRefreshRef.current = currentBooking.booking_id;
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
        text: `Đã giữ ô ${created.slot_id}. Bạn có thể xem đường đi hoặc hủy trước khi làm thủ tục vào bãi.`,
      });
      await refreshAllData();
    } catch (err) {
      if (err instanceof ApiError) {
        // Clear attempt key on deterministic conflict/4xx so user can pick another slot cleanly
        if (err.status >= 400 && err.status < 500) {
          bookingAttemptKeyRef.current = null;
        }
        if (err.status === 409) {
          setFeedbackBanner({
            type: "warning",
            text: err.message,
          });
        } else {
          setFeedbackBanner({
            type: "error",
            text: err.message,
          });
        }
      } else {
        setFeedbackBanner({
          type: "error",
          text: "Chưa xác nhận được đặt chỗ do mất kết nối. Kiểm tra lượt đặt hiện tại trước khi thử lại.",
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
        text: `Đã hủy đặt chỗ ô ${cancelled.slot_id}.`,
      });
      await refreshAllData();
    } catch (err) {
      setIsCancelConfirmOpen(false);
      if (err instanceof ApiError) {
        setFeedbackBanner({
          type: "error",
          text: err.message,
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

  const bookingStepIndex = !currentBooking ? -1 : currentBooking.status === "Reserved" ? 0 : currentBooking.status === "Checkin_pending" ? 1 : currentBooking.status === "Checked_in" ? 2 : 3;
  const selectedForMap = currentBooking?.slot_id || selectedSlotId;
  const bookingUnavailable = isBookingSubmitting || isInitialLoading || !!apiErrorBanner || !selectedSlotId || !primaryVehicle;

  return <AppShell user={user} onLogout={onLogout}>
    <div className="page-heading"><div><span className="eyebrow">Người gửi xe</span><h1>Chỗ đỗ của bạn</h1><p>{primaryVehicle ? `Phương tiện ${primaryVehicle.plate_display}` : "Tài khoản chưa có phương tiện được liên kết."}</p></div>
      <div className="row"><span className="muted small">{realtimeConnected ? "Đang đồng bộ" : "Cập nhật định kỳ"} · {lastUpdatedVn}</span><button className="button" disabled={isRefreshing} onClick={() => refreshAllData(true)}>{isRefreshing ? "Đang tải…" : "Làm mới"}</button></div>
    </div>
    {apiErrorBanner && <Notice tone="error">{apiErrorBanner} Dữ liệu hiển thị có thể chưa cập nhật; tạm ngừng đặt chỗ.</Notice>}
    {feedbackBanner && <Notice tone={feedbackBanner.type} onClose={() => setFeedbackBanner(null)}>{feedbackBanner.text}</Notice>}
    {isInitialLoading && <Notice>Đang tải trạng thái chỗ đỗ…</Notice>}

    <div className="booking-layout" id="booking">
      <section className="panel" aria-labelledby="floor-plan-title"><div className="panel-header"><div><h2 id="floor-plan-title">Sơ đồ bãi đỗ</h2><p>Chọn một ô còn trống để đặt giữ chỗ.</p></div><span className="small muted">{isInitialLoading || apiErrorBanner ? "—" : availableCount}/4 ô có thể đặt</span></div>
        <ParkingFloorPlan slots={slots} selectedId={selectedForMap} onSelect={setSelectedSlotId} disabled={!!currentBooking || !!apiErrorBanner || isInitialLoading} />
      </section>
      <aside className="panel" aria-labelledby="booking-title">
        <div className="panel-header"><h2 id="booking-title">{currentBooking ? "Lượt gửi xe hiện tại" : "Giữ chỗ"}</h2>{currentBooking && <StatusBadge status={currentBooking.status} />}</div>
        <div className="panel-body stack">
          {currentBooking ? <>
            <div className="row spread"><div><span className="eyebrow">Ô đỗ của bạn</span><strong className="booking-slot-number">{currentBooking.slot_id}</strong></div>
              {currentBooking.status === "Reserved" && <div style={{ textAlign: "right" }}><span className="small muted">Thời gian giữ chỗ còn lại</span><div className="booking-timer" style={{ color: countdownSeconds <= 300 ? "var(--danger)" : "var(--accent)" }}>{formatCountdownMMSS(countdownSeconds)}</div></div>}
            </div>
            <ol className="flow-steps" aria-label="Tiến trình gửi xe">{["Giữ chỗ", "Đối soát", "Trong bãi"].map((step, index) => <li className={bookingStepIndex >= index ? "is-current" : ""} key={step}>{step}</li>)}</ol>
            {currentBooking.status === "Checked_in" && <Notice tone={currentBooking.parking_status === "Parked_confirmed" ? "success" : "info"}>{statusLabel(currentBooking.parking_status)} · Đã gửi {Math.floor(parkedElapsedSeconds / 3600)} giờ {Math.floor((parkedElapsedSeconds % 3600) / 60)} phút</Notice>}
            <dl className="detail-list"><dt>Biển số</dt><dd className="mono">{currentBooking.plate_display || currentBooking.plate_number}</dd><dt>Đặt lúc</dt><dd>{formatVnDateTime(currentBooking.created_at)}</dd>
              {currentBooking.status === "Reserved" && <><dt>Giữ đến</dt><dd>{formatVnDateTime(currentBooking.expires_at)}</dd></>}
              {currentBooking.entry_time && <><dt>Vào bãi lúc</dt><dd>{formatVnDateTime(currentBooking.entry_time)}</dd></>}
            </dl>
            <button className="button button-primary button-full" onClick={() => setIsDriverModalOpen(true)}>Xem đường đến ô {currentBooking.slot_id}</button>
            {currentBooking.can_cancel && <button className="button button-quiet button-full" onClick={() => setIsCancelConfirmOpen(true)}>Hủy đặt chỗ</button>}
            {!currentBooking.can_cancel && <p className="small muted">Đặt chỗ không thể hủy khi xe đã bắt đầu làm thủ tục vào bãi.</p>}
          </> : <>
            {selectedSlotId ? <div className="row spread"><div><span className="eyebrow">Ô đang chọn</span><strong className="booking-slot-number">{selectedSlotId}</strong></div><span className="status-badge status-green">Giữ chỗ 60 phút</span></div> : <EmptyState>{isInitialLoading ? "Đang tải chỗ đỗ…" : "Hiện chưa có ô đủ điều kiện đặt chỗ."}</EmptyState>}
            <dl className="detail-list"><dt>Phương tiện</dt><dd className="mono">{primaryVehicle?.plate_display || "Chưa có phương tiện"}</dd><dt>Thời gian giữ</dt><dd>60 phút</dd></dl>
            <p className="small muted">Chỗ được giữ trong 60 phút. Hãy đến bãi trước khi đặt chỗ hết hạn.</p>
            <button className="button button-primary button-full" disabled={bookingUnavailable} onClick={handleBookSlot}>{isBookingSubmitting ? "Đang giữ chỗ…" : selectedSlotId ? `Giữ chỗ ô ${selectedSlotId}` : "Chưa có chỗ đỗ"}</button>
          </>}
        </div>
      </aside>
    </div>

    <section className="panel" id="history" aria-labelledby="history-title"><div className="panel-header"><div><h2 id="history-title">Lịch sử của bạn</h2><p>Các lần đặt chỗ và lượt gửi xe đã ghi nhận.</p></div>
      <div className="row"><button className={`button button-small ${activeHistoryTab === "bookings" ? "button-primary" : ""}`} onClick={() => setActiveHistoryTab("bookings")}>Đặt chỗ</button><button className={`button button-small ${activeHistoryTab === "sessions" ? "button-primary" : ""}`} onClick={() => setActiveHistoryTab("sessions")}>Lượt gửi xe</button>
        {activeHistoryTab === "bookings" && <select className="select small" aria-label="Lọc trạng thái đặt chỗ" style={{ width: "auto", maxWidth: "100%" }} value={historyStatusFilter} onChange={(event) => setHistoryStatusFilter(event.target.value)}><option value="">Tất cả trạng thái</option>{["Reserved", "Checkin_pending", "Checked_in", "Completed", "Expired", "Cancelled"].map((status) => <option key={status} value={status}>{statusLabel(status)}</option>)}</select>}
      </div>
    </div>
    {activeHistoryTab === "bookings" ? historyBookings.length === 0 ? <EmptyState>Chưa có đặt chỗ phù hợp.</EmptyState> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Ô đỗ</th><th>Biển số</th><th>Trạng thái</th><th>Thời gian đặt</th><th>Hết hạn / Kết thúc</th></tr></thead><tbody>{historyBookings.map((booking) => <tr key={booking.booking_id}><td><strong>{booking.slot_id}</strong></td><td className="mono">{booking.plate_display || booking.plate_number}</td><td><StatusBadge status={booking.status} /></td><td>{formatVnDateTime(booking.created_at)}</td><td>{formatVnDateTime(booking.cancelled_at || booking.completed_at || booking.expires_at)}</td></tr>)}</tbody></table></div>
      : historySessions.length === 0 ? <EmptyState>Chưa có lượt gửi xe được ghi nhận.</EmptyState> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Ô đỗ</th><th>Biển số</th><th>Trạng thái</th><th>Vị trí</th><th>Vào / Ra</th><th>Thời lượng</th></tr></thead><tbody>{historySessions.map((session) => <tr key={session.session_id}><td><strong>{session.assigned_slot_id}</strong></td><td className="mono">{session.plate_display || session.plate_number}</td><td><StatusBadge status={session.status} /></td><td>{statusLabel(session.parking_status)}</td><td><div>{formatVnDateTime(session.entry_time)}</div><span className="muted">{formatVnDateTime(session.exit_time)}</span></td><td>{formatDurationMinutes(session.entry_time, session.exit_time)}</td></tr>)}</tbody></table></div>}
    </section>

    {isCancelConfirmOpen && currentBooking && <ConfirmDialog title={`Hủy đặt chỗ ô ${currentBooking.slot_id}?`} pending={isCancelSubmitting} onClose={() => setIsCancelConfirmOpen(false)} onConfirm={handleConfirmCancelBooking}>Bạn sẽ không còn giữ ô này. Lịch sử đặt chỗ vẫn được lưu trong tài khoản.</ConfirmDialog>}
    {currentBooking && <FirstPersonDriverModal isOpen={isDriverModalOpen} onClose={() => setIsDriverModalOpen(false)} slotId={currentBooking.slot_id} plateDisplay={currentBooking.plate_display || currentBooking.plate_number || primaryVehicle?.plate_display || ""} bookingId={currentBooking.booking_id} />}
  </AppShell>;
};
