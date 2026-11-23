import React, { useCallback, useEffect, useState } from "react";
import { API_BASE_URL, ApiClient, ApiError } from "../../services/api.client";
import { ParkingService } from "../../services/parking.service";
import { ReviewService } from "../../services/review.service";
import { SessionService, GatewayStatus, AuditLogDTO } from "../../services/session.service";
import {
  BookingDTO,
  DeviceSensorHealth,
  ManualReviewItem,
  ParkingSlotView,
  SessionDTO,
  UserProfile,
} from "../../shared/types";

import { AppShell, Notice, StatusBadge, ParkingFloorPlan, SummaryStat, EmptyState, statusLabel } from "../../shared/components/ui";

interface AdminDashboardPageProps {
  user: UserProfile;
  onLogout: () => void;
}

interface CameraSnapshot {
  camera_id: string;
  image_base64: string | null;
  has_image?: boolean;
  captured_at?: string;
  expires_at?: string;
  event_id?: string;
  resolution?: number[];
  reason_code?: string;
  decision?: string;
  guidance?: { ok: boolean; reason_code: string; message: string; captured_at?: string; updated_at?: string };
  scan_state?: string;
  capture_round?: number;
  gate_id?: string;
  stream_id?: string;
  frame_sequence?: number;
  recognition?: {
    ok: boolean;
    reason_code: string;
    message: string;
    plate_number?: string;
    display_plate?: string;
    raw_text?: string;
    liveness_status?: string;
    liveness_score?: number | null;
    template_saved?: boolean;
    session_id?: string | null;
    similarity_score?: number | null;
  };
}

interface CameraStreamStatus {
  active: boolean;
  stream_id?: string | null;
  expires_at?: string | null;
  preview?: boolean;
  frames_received?: Record<string, number>;
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
    "overview" | "sessions" | "bookings" | "reviews" | "devices" | "logs" | "cameras"
  >("overview");

  const [slots, setSlots] = useState<ParkingSlotView[]>([]);
  const [availableCount, setAvailableCount] = useState<number>(0);
  const [sessions, setSessions] = useState<SessionDTO[]>([]);
  const [bookings, setBookings] = useState<BookingDTO[]>([]);
  const [reviews, setReviews] = useState<ManualReviewItem[]>([]);
  const [sensors, setSensors] = useState<DeviceSensorHealth[]>([]);
  const [overallDeviceStatus, setOverallDeviceStatus] = useState<string>("UNKNOWN");
  const [gateway, setGateway] = useState<GatewayStatus | null>(null);
  const [mqttConnected, setMqttConnected] = useState(false);
  const [logs, setLogs] = useState<AuditLogDTO[]>([]);
  const [pendingReview, setPendingReview] = useState<string | null>(null);
  const [serverOffsetMs, setServerOffsetMs] = useState(0);
  const [clockMs, setClockMs] = useState(Date.now());
  const [cameras, setCameras] = useState<CameraSnapshot[]>([]);
  const [cameraStream, setCameraStream] = useState<CameraStreamStatus>({ active: false });
  const [cameraIssue, setCameraIssue] = useState<string | null>(null);
  const [captureUntil, setCaptureUntil] = useState(0);
  const [reviewReasons, setReviewReasons] = useState<Record<string, string>>({});

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [actionIssue, setActionIssue] = useState<string | null>(null);
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [realtimeOnline, setRealtimeOnline] = useState<boolean>(false);

  const loadCameras = useCallback(async () => {
    try {
      const result = await ApiClient.get<{ cameras: CameraSnapshot[]; stream: CameraStreamStatus; server_time: string }>("/api/admin/cameras?images=0");
      setCameras(result.cameras);
      setCameraStream(result.stream || { active: false });
      setServerOffsetMs(Date.parse(result.server_time) - Date.now());
      setCameraIssue(null);
    } catch (error) {
      setCameras([]);
      setCameraStream({ active: false });
      setCameraIssue(error instanceof Error ? error.message : "Chưa tải được ảnh camera.");
    }
  }, []);

  useEffect(() => {
    if (!["overview", "cameras", "devices"].includes(activeTab)) {
      setCameras([]);
      return;
    }
    let active = true;
    let loading = false;
    const refresh = async () => {
      if (!active || loading) return;
      loading = true;
      try { await loadCameras(); } finally { loading = false; }
    };
    refresh();
    const timer = window.setInterval(refresh, 1000);
    return () => { active = false; window.clearInterval(timer); };
  }, [activeTab, loadCameras]);

  useEffect(() => {
    setCameras((previous) => previous.some((camera) => camera.image_base64 && Date.parse(camera.expires_at || "") <= clockMs + serverOffsetMs)
      ? previous.map((camera) => Date.parse(camera.expires_at || "") <= clockMs + serverOffsetMs ? { ...camera, image_base64: null } : camera)
      : previous);
  }, [clockMs, serverOffsetMs]);

  const captureCameras = async () => {
    setCaptureUntil(Date.now() + 6000);
    try {
      await ApiClient.post("/api/admin/cameras/capture");
      setActionFeedback("Đã yêu cầu hai camera chụp kiểm tra. Ảnh sẽ tự cập nhật; thao tác này không mở cổng.");
    } catch (error) {
      setCaptureUntil(0);
      setCameraIssue(error instanceof Error ? error.message : "Chưa gửi được yêu cầu chụp.");
    }
  };

  const controlCameraStream = async (action: "START" | "STOP") => {
    try {
      await ApiClient.post("/api/admin/cameras/stream", { action });
      setActionFeedback(action === "START" ? "Đã yêu cầu phát hình kiểm tra trong 30 giây. Thao tác này không mở cổng." : "Đã yêu cầu dừng phát hình.");
      await loadCameras();
    } catch (error) {
      setCameraIssue(error instanceof Error ? error.message : "Chưa điều khiển được camera.");
    }
  };

  const loadAdminData = useCallback(async () => {
    try {
      const [slotsRes, sessRes, bookRes, revRes, devRes, logRes] = await Promise.all([
        ParkingService.getSlots(),
        SessionService.listAdminSessions(),
        SessionService.listAdminBookings(),
        ReviewService.listAdminReviews(false),
        SessionService.getAdminDevices(),
        SessionService.listAdminLogs(),
      ]);
      setSlots(slotsRes.slots);
      setAvailableCount(slotsRes.available_count);
      setSessions(sessRes.sessions);
      setBookings(bookRes.bookings);
      setReviews(revRes.reviews);
      setSensors(devRes.sensors);
      setOverallDeviceStatus(devRes.overall_status);
      setGateway(devRes.gateway || null);
      setMqttConnected(devRes.mqtt?.connected === true);
      setLogs(logRes.logs);
      setServerOffsetMs(Date.parse(bookRes.server_time) - Date.now());
      setApiError(null);
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.message);
      } else {
        setApiError("Không thể kết nối máy chủ để cập nhật bãi đỗ.");
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAdminData();
    const poll = window.setInterval(loadAdminData, 5000);
    const tick = window.setInterval(() => setClockMs(Date.now()), 1000);
    return () => { window.clearInterval(poll); window.clearInterval(tick); };
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
    const reason = (reviewReasons[eventId] || "").trim();
    if (!reason || pendingReview) return;
    setPendingReview(eventId);
    setActionFeedback(null);
    setActionIssue(null);
    setApiError(null);
    try {
      const decision = await ReviewService.submitDecision(eventId, action, reason);
      if (decision.command_status === "PUBLISH_FAILED") {
        setActionIssue("Đã lưu quyết định nhưng chưa gửi được lệnh tới thiết bị. Kiểm tra kết nối và tình trạng cổng trước khi thao tác tiếp.");
        return;
      }
      setActionFeedback(
        action === "APPROVE" ? "Đã lưu quyết định cho phép. Theo dõi phản hồi tại mục Thiết bị." : "Đã ghi nhận quyết định từ chối."
      );
      await loadAdminData();
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.message);
      } else {
        setApiError("Chưa xác nhận được quyết định. Tải lại dữ liệu để kiểm tra trước khi thử tiếp.");
      }
    } finally {
      setPendingReview(null);
    }
  };

  const activeSessionsCount = sessions.filter((s) =>
    ["Entry_pending", "Active", "Exit_pending"].includes(s.status)
  ).length;
  const activeBookingsCount = bookings.filter((b) =>
    ["Reserved", "Checkin_pending"].includes(b.status)
  ).length;

  const navigation = <>{[
    { id: "overview", label: "Tổng quan" }, { id: "sessions", label: "Lượt gửi xe" },
    { id: "bookings", label: "Đặt chỗ" }, { id: "reviews", label: "Cần kiểm tra" },
    { id: "devices", label: "Thiết bị" }, { id: "logs", label: "Nhật ký" },
    { id: "cameras", label: "Camera" },
  ].map((tab) => <button key={tab.id} className={`nav-tab ${activeTab === tab.id ? "is-active" : ""}`} aria-current={activeTab === tab.id ? "page" : undefined} onClick={() => setActiveTab(tab.id as typeof activeTab)}>{tab.label}{tab.id === "reviews" && reviews.length > 0 && <span className="tab-count">{reviews.length}</span>}</button>)}</>;
  const tabTitles: Record<string, string> = { overview: "Tình hình bãi đỗ", sessions: "Lượt gửi xe", bookings: "Đặt chỗ", reviews: "Các trường hợp cần kiểm tra", devices: "Thiết bị và kết nối", logs: "Nhật ký vận hành", cameras: "Camera tại cổng" };
  const visibleSessions = activeTab === "overview" ? sessions.filter((session) => ["Entry_pending", "Active", "Exit_pending"].includes(session.status)).slice(0, 6) : sessions;

  return <AppShell user={user} onLogout={onLogout} navigation={navigation}>
    <div className="page-heading"><div><span className="eyebrow">Quản lý bãi đỗ</span><h1>{tabTitles[activeTab]}</h1><p>Theo dõi 4 ô đỗ và xử lý các lượt xe trong bãi.</p></div><div className="row"><span className="small muted">{realtimeOnline ? "Đang đồng bộ" : "Cập nhật mỗi 5 giây"}</span><button className="button" onClick={loadAdminData}>Làm mới</button></div></div>
    {apiError && <Notice tone="error">{apiError} Dữ liệu hiển thị có thể chưa cập nhật.</Notice>}
    {actionFeedback && <Notice tone="success" onClose={() => setActionFeedback(null)}>{actionFeedback}</Notice>}
    {actionIssue && <Notice tone="error" onClose={() => setActionIssue(null)}>{actionIssue}</Notice>}
    {isLoading && <Notice>Đang tải dữ liệu bãi đỗ…</Notice>}
    <div className="summary-grid"><SummaryStat label="Ô có thể nhận xe" value={isLoading || apiError ? "—" : `${availableCount}/4`} detail="Theo trạng thái và quyền giữ ô" /><SummaryStat label="Xe đang trong lượt gửi" value={isLoading ? "—" : activeSessionsCount} detail="Gồm lượt đang qua cổng" /><SummaryStat label="Đặt chỗ đang giữ" value={isLoading ? "—" : activeBookingsCount} detail="Đang giữ hoặc đang đối soát" /><SummaryStat label="Cần kiểm tra" value={isLoading ? "—" : reviews.length} detail="Cổng vào, cổng ra và vị trí đỗ" /></div>

    {["overview", "cameras", "devices"].includes(activeTab) && <section className="panel">
      <div className="panel-header"><div><h2>Camera tại cổng</h2><p>IR phát hiện xe sẽ bật hai camera; kết thúc lượt thì dừng. Xem trực tiếp MJPEG, mục tiêu 5 khung/giây mỗi bo.</p></div>
        <div className="row"><button className="button" disabled={!mqttConnected || clockMs < captureUntil || cameraStream.active} onClick={captureCameras}>{clockMs < captureUntil ? "Đang chờ ảnh…" : "Chụp một ảnh"}</button>
        {cameraStream.active ? <button className="button" onClick={() => controlCameraStream("STOP")}>Dừng phát hình</button>
          : <button className="button button-primary" disabled={!mqttConnected} onClick={() => controlCameraStream("START")}>Xem trực tiếp 30 giây</button>}</div></div>
      <div className="panel-body small muted" style={{ paddingBottom: 0 }}>{cameraStream.active ? (cameraStream.preview ? "Đang phát hình kiểm tra" : "Đang phát hình theo lượt xe") : "Đã dừng phát hình. Ảnh cuối tự hết hạn sau 30 giây."}</div>
      {cameraIssue && <Notice tone="error">{cameraIssue}</Notice>}
      <div className="panel-body device-grid">{["cam_plate", "cam_face"].map((id) => {
        const camera = cameras.find((item) => item.camera_id === id);
        const visible = camera?.has_image && Date.parse(camera.expires_at || "") > clockMs + serverOffsetMs;
        const live = cameraStream.active && cameraStream.stream_id;
        const cameraUrl = live
          ? `${API_BASE_URL}/api/admin/cameras/${id}/mjpeg?stream_id=${encodeURIComponent(cameraStream.stream_id!)}`
          : `${API_BASE_URL}/api/admin/cameras/${id}/image?t=${encodeURIComponent(camera?.captured_at || "")}`;
        const fresh = cameraStream.active && camera?.stream_id === cameraStream.stream_id && clockMs + serverOffsetMs - Date.parse(camera?.captured_at || "") < 3000;
        return <article className="device-card stack" key={id}>
          <div className="row spread"><h3>{id === "cam_plate" ? "Camera biển số" : "Camera khuôn mặt"}</h3><span className="small muted">{cameraStream.active ? (fresh ? "Đang nhận hình" : "Chờ khung hình") : "Ảnh gần nhất"}</span></div>
          {live || visible ? <img key={cameraUrl} alt={id === "cam_plate" ? "Ảnh biển số gần nhất tại cổng" : "Ảnh khuôn mặt gần nhất tại cổng"} src={cameraUrl} style={{ width: "100%", maxHeight: 320, objectFit: "contain", background: "#17211c", borderRadius: 6 }} />
            : <EmptyState>Chưa có ảnh mới. Đưa xe tới IR cổng vào hoặc bấm chụp kiểm tra.</EmptyState>}
          {id === "cam_face" && cameraStream.active && clockMs + serverOffsetMs < Date.parse(cameraStream.expires_at || "") && camera?.guidance && (!camera.guidance.captured_at || clockMs + serverOffsetMs - Date.parse(camera.guidance.captured_at) < 3000) && <div role="status" className="small" style={{ padding: 10, borderRadius: 6, background: camera.guidance.ok ? "#e8f5e9" : "#fff3cd", color: "#17211c" }}><strong>{camera.guidance.message}</strong><div>Hướng dẫn tư thế trực tiếp; kết quả duyệt lượt xe hiển thị riêng bên dưới.</div></div>}
          {camera?.decision === "Scanning" && <span className="small">Đang tự quét lại — lần {camera?.capture_round || 1}. Giữ biển số và khuôn mặt rõ trong khung hình.</span>}
          {visible && <><span className="small muted">{formatAdminVnDateTime(camera.captured_at)} · {camera.resolution?.join(" × ")}</span>{cameraStream.active && <span className="small muted">Đã nhận {cameraStream.frames_received?.[id] || 0} khung hình</span>}{camera.reason_code && camera.decision !== "Scanning" && <span className="small">Kết quả lượt xe: {camera.reason_code === "FACE_REVIEW_REQUIRED" ? "Cần kiểm tra thủ công vì khuôn mặt chưa đủ điểm đối chiếu" : camera.reason_code}</span>}</>}
          {visible && camera.recognition && <div className="stack small" aria-label="Kết quả nhận diện AI">
            <strong>{id === "cam_plate"
              ? (camera.recognition.ok ? `Biển số: ${camera.recognition.display_plate || camera.recognition.plate_number}` : `OCR chưa đạt${camera.recognition.raw_text ? `: ${camera.recognition.raw_text}` : ""}`)
              : (camera.recognition.ok ? "Đã trích xuất đặc trưng khuôn mặt" : "Ảnh khuôn mặt chưa đạt")}</strong>
            <span>{camera.recognition.message}</span>
            {camera.recognition.liveness_status && <span>Kiểm tra người thật: {camera.recognition.liveness_status === "Passed" ? "Đạt" : "Chưa đạt"}</span>}
            {camera.recognition.template_saved && <span>Đã lưu mẫu khuôn mặt vào phiên {camera.recognition.session_id}.</span>}
            {camera.recognition.similarity_score != null && <span><strong>Đối chiếu khuôn mặt: {camera.decision === "Approved" ? "Đã đạt" : "Chưa được duyệt"}.</strong> Điểm: {camera.recognition.similarity_score.toFixed(3)}</span>}
          </div>}
        </article>;
      })}</div>
    </section>}

    {activeTab === "overview" && <div className="booking-layout"><section className="panel"><div className="panel-header"><h2>Sơ đồ bãi đỗ</h2><span className="small muted">A1 · A2 · B1 · B2</span></div><ParkingFloorPlan slots={slots} admin /></section>
      <aside className="panel"><div className="panel-header"><h2>Tình trạng vận hành</h2></div><div className="panel-body stack"><div className="row spread"><span>Cảm biến ô đỗ</span><StatusBadge status={overallDeviceStatus === "HEALTHY" ? "AVAILABLE" : "UNKNOWN_OR_FAULT"} label={overallDeviceStatus === "HEALTHY" ? "Dữ liệu hợp lệ" : "Cần kiểm tra"} /></div><div className="row spread"><span>Kết nối thiết bị</span><StatusBadge status={mqttConnected ? "AVAILABLE" : "UNKNOWN_OR_FAULT"} label={mqttConnected ? "Đã kết nối" : "Chưa kết nối"} /></div><div className="section-rule" style={{ margin: 0 }} />
        <p className="small muted">{reviews.length ? `Có ${reviews.length} trường hợp cần quản trị viên kiểm tra trước khi xử lý tiếp.` : "Chưa có trường hợp cần kiểm tra trong dữ liệu hiện tại."}</p>
        <button className="button button-full" onClick={() => setActiveTab("reviews")}>Xem các trường hợp cần kiểm tra</button><button className="button button-quiet button-full" onClick={() => setActiveTab("devices")}>Xem tình trạng thiết bị</button>
      </div></aside></div>}

    {(activeTab === "overview" || activeTab === "sessions") && <section className="panel"><div className="panel-header"><h2>{activeTab === "overview" ? "Lượt xe đang xử lý" : "Lượt gửi xe và lịch sử"}</h2><span className="small muted">{visibleSessions.length} lượt</span></div>{visibleSessions.length === 0 ? <EmptyState>Chưa có lượt gửi xe phù hợp.</EmptyState> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Biển số</th><th>Ô đỗ</th><th>Trạng thái</th><th>Vị trí đỗ</th><th>Vào bãi</th><th>Rời bãi</th></tr></thead><tbody>{visibleSessions.map((session) => <tr key={session.session_id}><td className="mono">{session.plate_display || session.plate_number}</td><td><strong>{session.assigned_slot_id}</strong></td><td><StatusBadge status={session.status} /></td><td>{statusLabel(session.parking_status)}</td><td>{formatAdminVnDateTime(session.entry_time)}</td><td>{formatAdminVnDateTime(session.exit_time)}</td></tr>)}</tbody></table></div>}</section>}

    {activeTab === "bookings" && <section className="panel"><div className="panel-header"><h2>Các lần đặt chỗ</h2><span className="small muted">Tối đa 100 bản ghi gần nhất</span></div>{bookings.length === 0 ? <EmptyState>Chưa có đặt chỗ được ghi nhận.</EmptyState> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Người đặt</th><th>Biển số</th><th>Ô đỗ</th><th>Trạng thái</th><th>Thời gian đặt</th><th>Giữ đến</th></tr></thead><tbody>{bookings.map((booking) => <tr key={booking.booking_id}><td>{booking.display_name || booking.username || `Tài khoản ${booking.user_id}`}</td><td className="mono">{booking.plate_display || booking.plate_number}</td><td><strong>{booking.slot_id}</strong></td><td><StatusBadge status={booking.status} /></td><td>{formatAdminVnDateTime(booking.created_at)}</td><td><div>{formatAdminVnDateTime(booking.expires_at)}</div>{booking.status === "Reserved" && <span className="small muted">Còn {Math.max(0, Math.ceil((Date.parse(booking.expires_at) - clockMs - serverOffsetMs) / 60000))} phút</span>}</td></tr>)}</tbody></table></div>}</section>}

    {activeTab === "reviews" && <section className="panel"><div className="panel-header"><div><h2>Chờ quyết định</h2><p>Kiểm tra tình huống thực tế và ghi lý do trước khi xử lý.</p></div></div>{reviews.length === 0 ? <EmptyState>Không có trường hợp đang chờ kiểm tra.</EmptyState> : <div className="review-list">{reviews.map((review) => <article className="review-item" key={review.event_id}><div className="stack" style={{ gap: 9 }}><div className="row"><h3>{review.review_type === "PARKING_ANOMALY" ? "Kiểm tra vị trí đỗ" : `Kiểm tra cổng ${review.gate_id === "IN" ? "vào" : "ra"}`}</h3><StatusBadge status={review.decision} /></div><p><strong className="mono">{review.plate_display || review.plate_number || "Chưa xác định biển số"}</strong>{review.slot_id ? ` · Ô ${review.slot_id}` : ""}</p><span className="small muted">{formatAdminVnDateTime(review.created_at)} · {review.reason_code || "Chưa rõ nguyên nhân"}</span><span className="small mono muted" style={{ overflowWrap: "anywhere" }}>{review.event_id}</span></div>
      <div className="review-actions"><label className="small" htmlFor={`reason-${review.event_id}`}>Lý do xử lý</label><input className="input" id={`reason-${review.event_id}`} placeholder="Nhập kết quả kiểm tra…" value={reviewReasons[review.event_id] || ""} onChange={(event) => setReviewReasons((previous) => ({ ...previous, [review.event_id]: event.target.value }))} /><div className="row"><button className="button button-primary" disabled={pendingReview !== null || !!apiError || !(reviewReasons[review.event_id] || "").trim()} onClick={() => handleReviewDecision(review.event_id, "APPROVE")}>{pendingReview === review.event_id ? "Đang xử lý…" : "Cho phép"}</button><button className="button" disabled={pendingReview !== null || !!apiError || !(reviewReasons[review.event_id] || "").trim()} onClick={() => handleReviewDecision(review.event_id, "DENY")}>Từ chối</button></div></div>
    </article>)}</div>}</section>}

    {activeTab === "devices" && <>
      <section className="panel"><div className="panel-header"><h2>Kết nối và camera</h2><StatusBadge status={mqttConnected ? "AVAILABLE" : "UNKNOWN_OR_FAULT"} label={mqttConnected ? "MQTT đã kết nối" : "MQTT chưa kết nối"} /></div><div className="panel-body stack"><div className="device-grid">{gateway?.devices.map((device) => <div className="device-card stack" key={device.device_id} style={{ gap: 10 }}><div className="row spread"><h3>{device.device_id === "s3_plate_ctrl" ? "Camera biển số / Điều khiển" : "Camera khuôn mặt"}</h3><StatusBadge status={device.online ? "AVAILABLE" : "UNKNOWN_OR_FAULT"} label={device.online ? "Trực tuyến" : "Chưa có kết nối"} /></div><span className="small muted mono">{device.device_id}</span><dl className="detail-list"><dt>Camera</dt><dd>{device.camera_ready ? "Sẵn sàng" : "Chưa sẵn sàng"}</dd><dt>Nhận tín hiệu gần nhất</dt><dd>{device.age_seconds === null ? "Chưa có" : `${device.age_seconds} giây trước`}</dd></dl></div>)}</div>
      <dl className="detail-list"><dt>Model AI</dt><dd>{statusLabel(gateway?.ai_status)}</dd><dt>Lượt nhận diện hiện tại</dt><dd className="mono">{gateway?.active_event_id || "Không có"}</dd><dt>Số lượt đang chờ</dt><dd>{gateway?.queue_length ?? "—"}</dd></dl>
      </div></section>
      <section className="panel"><div className="panel-header"><h2>Cảm biến bốn ô đỗ</h2></div>{sensors.length === 0 ? <EmptyState>Chưa có dữ liệu cảm biến.</EmptyState> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Ô đỗ</th><th>Cảm biến</th><th>Trạng thái vật lý</th><th>Độ mới dữ liệu</th><th>Nhận lần cuối</th></tr></thead><tbody>{sensors.map((sensor) => <tr key={sensor.slot_id}><td><strong>{sensor.slot_id}</strong></td><td className="mono">{sensor.sensor_id}</td><td>{statusLabel(sensor.physical_status)}</td><td><StatusBadge status={sensor.is_fresh && !sensor.is_fault ? "AVAILABLE" : "UNKNOWN_OR_FAULT"} label={sensor.is_fresh && !sensor.is_fault ? `Hợp lệ · ${sensor.age_seconds ?? 0}s` : "Quá hạn / Chưa rõ"} /></td><td>{formatAdminVnDateTime(sensor.last_seen_at)}</td></tr>)}</tbody></table></div>}</section>
      <section className="panel"><div className="panel-header"><div><h2>Phản hồi lệnh điều khiển</h2><p>Thiết bị nhận lệnh chưa có nghĩa là xe đã qua cổng.</p></div></div>{!gateway?.commands.length ? <EmptyState>Chưa có lệnh điều khiển.</EmptyState> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Lượt cổng</th><th>Lệnh</th><th>Phản hồi thiết bị</th></tr></thead><tbody>{gateway.commands.slice(-10).reverse().map((command) => <tr key={command.command_id}><td className="mono small">{command.event_id}</td><td>{command.action === "OPEN" ? "Cho phép mở" : command.action === "DENY" ? "Từ chối" : "Giữ để kiểm tra"}</td><td><StatusBadge status={command.delivery_status} /></td></tr>)}</tbody></table></div>}</section>
    </>}

    {activeTab === "logs" && <section className="panel"><div className="panel-header"><h2>Hoạt động gần đây</h2><span className="small muted">50 bản ghi gần nhất</span></div>{logs.length === 0 ? <EmptyState>Chưa có hoạt động được ghi nhận.</EmptyState> : <div className="table-wrap"><table className="data-table"><thead><tr><th>Thời gian</th><th>Hoạt động</th><th>Chi tiết</th><th>Người thực hiện</th></tr></thead><tbody>{logs.map((log) => <tr key={log.log_id}><td>{formatAdminVnDateTime(log.created_at)}</td><td className="mono small">{log.event_type}</td><td className="small">{log.reason_code || "—"}<div className="muted mono">{log.event_id}</div></td><td>{log.actor_user_id ? `Tài khoản ${log.actor_user_id}` : "Hệ thống"}</td></tr>)}</tbody></table></div>}</section>}
  </AppShell>;
};
