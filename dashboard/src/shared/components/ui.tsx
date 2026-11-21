import React from "react";
import { ParkingSlotView, SlotId, UserProfile } from "../types";

export function ParkingBrand() {
  return <span className="parking-brand"><span className="parking-brand-mark" aria-hidden="true">P</span><span>Bãi đỗ <strong>PBL4</strong></span></span>;
}

export function AppShell({ user, onLogout, children, navigation }: {
  user: UserProfile; onLogout: () => void; children: React.ReactNode; navigation?: React.ReactNode;
}) {
  return <div className="app-shell">
    <header className="app-header"><div className="app-header-inner"><a href={user.role === "admin" ? "/admin" : "/user"} className="brand-link" aria-label="Trang chủ"><ParkingBrand /></a>
      <div className="account-menu"><span className="role-label">{user.role === "admin" ? "Quản trị" : "Người gửi xe"}</span><span className="account-name">{user.display_name || user.username}</span><button className="button button-quiet" onClick={onLogout}>Đăng xuất</button></div>
    </div>{navigation && <nav className="app-navigation" aria-label="Điều hướng">{navigation}</nav>}</header>
    <main className="app-main">{children}</main>
    <footer className="app-footer"><span>Bãi đỗ PBL4</span><span>Sa bàn 4 ô · Đại học Bách khoa Đà Nẵng</span></footer>
  </div>;
}

export function Notice({ children, tone = "info", onClose }: { children: React.ReactNode; tone?: "info" | "success" | "warning" | "error"; onClose?: () => void }) {
  return <div className={`notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}><span>{children}</span>{onClose && <button className="notice-close" aria-label="Đóng thông báo" onClick={onClose}>×</button>}</div>;
}

const statusLabels: Record<string, string> = {
  NOT_INITIALIZED: "Chưa khởi tạo", FACE_MODEL_MISSING: "Thiếu model khuôn mặt", FACE_MODEL_UNAVAILABLE: "Không tải được model khuôn mặt", LIVENESS_MISSING: "Thiếu model liveness", READY: "Đã nạp model",
  AVAILABLE: "Có thể đặt", RESERVED: "Đã giữ chỗ", ASSIGNED_PENDING: "Chờ xe vào ô", OCCUPIED: "Đang có xe", UNKNOWN_OR_FAULT: "Chưa rõ trạng thái",
  Reserved: "Đang giữ chỗ", Checkin_pending: "Đang đối soát", Checked_in: "Đã vào bãi", Completed: "Hoàn tất", Expired: "Hết hạn", Cancelled: "Đã hủy",
  Entry_pending: "Chờ qua cổng vào", Active: "Đang gửi xe", Exit_pending: "Chờ qua cổng ra", Closed: "Đã rời bãi",
  Not_arrived: "Chưa đến ô", Parking_pending: "Chờ đỗ xe", Parked_confirmed: "Đã đỗ đúng ô", Parking_review_required: "Cần kiểm tra vị trí", Parking_timeout: "Quá thời gian đỗ",
  Pending: "Chờ xử lý", Approved: "Đã cho phép", Denied: "Đã từ chối", Review_required: "Cần kiểm tra",
  Free: "Trống", Occupied: "Có xe", Unknown: "Chưa có dữ liệu", Fault: "Lỗi cảm biến",
  ACK_ACCEPTED: "Thiết bị đã nhận", ACK_REJECTED: "Thiết bị từ chối", PENDING_ACK: "Chờ thiết bị phản hồi", ACK_TIMEOUT: "Quá hạn phản hồi", PUBLISH_FAILED: "Chưa gửi được lệnh",
};

export function statusLabel(status: string | null | undefined): string {
  return status ? statusLabels[status] || status : "Chưa có dữ liệu";
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const tone = ["AVAILABLE", "Completed", "Parked_confirmed", "ACK_ACCEPTED"].includes(status) ? "green"
    : ["UNKNOWN_OR_FAULT", "Fault", "Parking_timeout", "PUBLISH_FAILED", "ACK_REJECTED", "ACK_TIMEOUT", "Denied"].includes(status) ? "red"
    : ["RESERVED", "Reserved", "Checkin_pending", "Pending", "Review_required", "Parking_review_required", "PENDING_ACK"].includes(status) ? "amber"
    : ["OCCUPIED", "Active", "Checked_in", "ASSIGNED_PENDING", "Entry_pending", "Exit_pending"].includes(status) ? "blue" : "neutral";
  return <span className={`status-badge status-${tone}`}><span className="status-dot" aria-hidden="true" />{label || statusLabel(status)}</span>;
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

export function SummaryStat({ label, value, detail }: { label: string; value: React.ReactNode; detail?: string }) {
  return <div className="summary-stat"><span className="summary-label">{label}</span><strong className="summary-value">{value}</strong>{detail && <span className="muted small">{detail}</span>}</div>;
}

export function ConfirmDialog({ title, children, pending, onClose, onConfirm }: {
  title: string; children: React.ReactNode; pending: boolean; onClose: () => void; onConfirm: () => void;
}) {
  const dialogRef = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const first = dialogRef.current?.querySelector<HTMLButtonElement>("button");
    first?.focus();
    return () => previous?.focus();
  }, []);
  return <div className="modal-backdrop" onClick={(event) => { if (event.target === event.currentTarget && !pending) onClose(); }}>
    <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title" ref={dialogRef} tabIndex={-1}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !pending) onClose();
        if (event.key === "Tab") {
          const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"));
          if (!buttons.length) { event.preventDefault(); event.currentTarget.focus(); return; }
          const first = buttons[0], last = buttons[buttons.length - 1];
          if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
          if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
        }
      }}>
      <h2 id="confirm-dialog-title">{title}</h2><p>{children}</p>
      <div className="row" style={{ justifyContent: "flex-end" }}><button className="button" onClick={onClose} disabled={pending}>Giữ đặt chỗ</button><button className="button button-danger" onClick={onConfirm} disabled={pending}>{pending ? "Đang hủy…" : "Xác nhận hủy"}</button></div>
    </div>
  </div>;
}

export function ParkingFloorPlan({ slots, selectedId, onSelect, disabled = false, admin = false }: {
  slots: ParkingSlotView[]; selectedId?: SlotId | null; onSelect?: (id: SlotId) => void; disabled?: boolean; admin?: boolean;
}) {
  return <div className="floor-plan"><div className="floor-plan-top"><span>Vị trí ô đỗ</span><span>IN <span aria-hidden="true">→</span> Lối vào</span></div>
    {([['A1', 'A2'], ['B1', 'B2']] as SlotId[][]).map((row, index) => <React.Fragment key={index}>
      {index === 1 && <div className="parking-aisle"><span>Lối xe lưu thông</span><span aria-hidden="true">↓</span></div>}
      <div className="parking-row">{row.map((id) => {
        const slot = slots.find((item) => item.slot_id === id);
        const state = slot?.display_status || "UNKNOWN_OR_FAULT";
        const canSelect = !!slot?.is_bookable && !disabled && !!onSelect;
        const selected = selectedId === id;
        const mine = slot?.is_my_booking || slot?.is_my_session;
        return <button key={id} type="button" className={`parking-bay bay-${state.toLowerCase()} ${selected ? "is-selected" : ""}`}
          disabled={!canSelect} aria-pressed={selected} aria-label={`Ô ${id} · ${statusLabel(state)}`}
          onClick={() => canSelect && onSelect?.(id)}>
          <span className="bay-top"><strong className="bay-number">{id}</strong>{mine ? <span className="bay-selected">Của bạn</span> : selected ? <span className="bay-selected">Đang chọn</span> : null}</span>
          <StatusBadge status={state} />
          <span className="bay-caption">{slot && (admin || mine) && slot.plate_display ? slot.plate_display : state === "AVAILABLE" ? "Chọn để giữ chỗ 60 phút" : state === "UNKNOWN_OR_FAULT" ? "Chờ dữ liệu cảm biến" : statusLabel(state)}</span>
        </button>;
      })}</div>
    </React.Fragment>)}
    <div className="floor-plan-bottom"><span>OUT <span aria-hidden="true">←</span> Lối ra</span><span>Hàng A / Hàng B</span></div>
    <div className="floor-plan-legend"><StatusBadge status="AVAILABLE" /><StatusBadge status="RESERVED" /><StatusBadge status="OCCUPIED" /><StatusBadge status="UNKNOWN_OR_FAULT" label="Chưa rõ" /></div>
  </div>;
}
