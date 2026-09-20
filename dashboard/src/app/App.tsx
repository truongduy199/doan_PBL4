import React, { useState, useEffect } from "react";
import { Header } from "../shared/components/Header";
import { Navbar } from "../shared/components/Navbar";
import { CameraDrawer } from "../features/cameras/CameraDrawer";
import { ParkingSlotsGrid } from "../features/parking-slots/ParkingSlotsGrid";
import { ActiveSessionsTable } from "../features/active-sessions/ActiveSessionsTable";
import { ManualReviewPanel } from "../features/manual-review/ManualReviewPanel";
import { RealtimeEventsLog } from "../features/alerts/RealtimeEventsLog";
import { ParkingService, defaultSlots } from "../services/parking.service";
import { SessionService, initialSessions } from "../services/session.service";
import { ReviewService, defaultReview } from "../services/review.service";
import { ParkingSlot, ParkingSession, ReviewRequest, SystemEventLog } from "../shared/types";

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [isCameraOpen, setIsCameraOpen] = useState<boolean>(false);
  const [cameraStatusText, setCameraStatusText] = useState<string>("Chế độ chờ");

  const [slots, setSlots] = useState<ParkingSlot[]>(defaultSlots);
  const [sessions, setSessions] = useState<ParkingSession[]>(initialSessions);
  const [review, setReview] = useState<ReviewRequest | null>(defaultReview);

  const [logs, setLogs] = useState<SystemEventLog[]>([
    { id: "1", type: "ENTRY", title: "Xe vào: 92B-678.90", description: "Đã cấp ô đỗ B1. Barie cổng vào mở và đóng an toàn.", timestamp: "14:42:05", severity: "success" },
    { id: "2", type: "REVIEW", title: "Ngoại lệ cổng ra: 43A-123.45", description: "Độ khớp mặt 0.58. Đã tạo yêu cầu xác nhận REQ-01.", timestamp: "14:41:50", severity: "warning" },
    { id: "3", type: "SLOT", title: "Cập nhật ô A1: CÓ XE", description: "Camera toàn cảnh xác nhận xe đã đỗ đúng vị trí.", timestamp: "14:20:45", severity: "info" },
  ]);

  // Lắng nghe dữ liệu thời gian thực từ Firebase Realtime Database
  useEffect(() => {
    const unsubSlots = ParkingService.subscribeSlots((newSlots) => setSlots(newSlots));
    const unsubSessions = SessionService.subscribeSessions((newSessions) => setSessions(newSessions));
    const unsubReviews = ReviewService.subscribeReviews((newReview) => setReview(newReview));

    return () => {
      unsubSlots();
      unsubSessions();
      unsubReviews();
    };
  }, []);

  // Kịch bản demo: Xe tới cổng -> Tự động mở 3 ô camera
  const handleSimulateArrival = () => {
    setIsCameraOpen(true);
    setCameraStatusText("🔴 Đang chụp biển số & mặt tại cổng vào...");

    const newLog: SystemEventLog = {
      id: Date.now().toString(),
      type: "TRIGGER",
      title: "Cảm biến cổng vào kích hoạt",
      description: "Phát hiện xe tới cổng. Hệ thống tự động kích hoạt 3 camera quan sát.",
      timestamp: new Date().toLocaleTimeString("vi-VN"),
      severity: "info",
    };
    setLogs((prev) => [newLog, ...prev]);
  };

  // Kịch bản demo: Xe đã đỗ đúng ô -> Tự động thu gọn 3 ô camera
  const handleSimulateParked = () => {
    setIsCameraOpen(false);
    setCameraStatusText("Chế độ chờ");

    // Cập nhật ô B1 thành OCCUPIED
    setSlots((prev) =>
      prev.map((s) => (s.slot_id === "B1" ? { ...s, status: "OCCUPIED" } : s))
    );

    const newLog: SystemEventLog = {
      id: Date.now().toString(),
      type: "PARKED",
      title: "Xe 92B-678.90 đã vào ô B1",
      description: "Camera toàn cảnh xác nhận xe đã đỗ đúng vị trí. Tự động thu gọn camera.",
      timestamp: new Date().toLocaleTimeString("vi-VN"),
      severity: "success",
    };
    setLogs((prev) => [newLog, ...prev]);
  };

  const handleReviewDecision = async (requestId: string, approved: boolean) => {
    await ReviewService.submitDecision(requestId, approved ? "APPROVED" : "REJECTED");
    if (review) {
      setReview({ ...review, status: approved ? "APPROVED" : "REJECTED" });
    }
    const newLog: SystemEventLog = {
      id: Date.now().toString(),
      type: "REVIEW_DECISION",
      title: approved ? "Đã duyệt mở cổng ra" : "Đã từ chối cổng ra",
      description: approved
        ? "Cán bộ quản trị đã chấp thuận cho xe ra qua cổng."
        : "Cán bộ quản trị từ chối yêu cầu ra của xe.",
      timestamp: new Date().toLocaleTimeString("vi-VN"),
      severity: approved ? "success" : "warning",
    };
    setLogs((prev) => [newLog, ...prev]);
  };

  const freeSlotsCount = slots.filter((s) => s.status === "FREE").length;

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 text-slate-800">
      {/* Header & Navbar */}
      <Header />
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* 3 Camera Drawer (Nút chữ nhật dọc sát lề trái với mũi tên tam giác tù) */}
      <CameraDrawer
        isOpen={isCameraOpen}
        setIsOpen={setIsCameraOpen}
        cameraStatusText={cameraStatusText}
      />

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 py-5 flex-1 w-full space-y-6">
        {/* Banner Mô phỏng Kịch bản kiểm thử */}
        <div className="bg-white border border-blue-200 rounded-xl p-3 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded text-[11px]">
              MÔ PHỎNG SỰ KIỆN
            </span>
            <span className="text-slate-700 font-medium">
              Kiểm tra tính năng tự động mở camera khi có xe đến cổng và tự thu gọn khi đỗ đúng vị trí:
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleSimulateArrival}
              className="bg-[#004b87] hover:bg-[#003870] text-white px-3 py-1.5 rounded font-semibold transition shadow-sm cursor-pointer"
            >
              🚗 Giả lập: Xe tới cổng (Mở Camera)
            </button>
            <button
              onClick={handleSimulateParked}
              className="bg-slate-200 hover:bg-slate-300 text-slate-700 px-3 py-1.5 rounded font-semibold transition cursor-pointer"
            >
              🅿️ Xe đã vào ô (Đóng Camera)
            </button>
          </div>
        </div>

        {/* Quick KPI Summary Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white border border-slate-300 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
              <span>Ô ĐỖ KHẢ DỤNG</span>
              <span className="text-emerald-600 text-base">🟢</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-[#004b87] tracking-tight">
                {freeSlotsCount}
              </span>
              <span className="text-xs text-slate-500">/ 4 vị trí</span>
            </div>
            <div className="mt-1 text-xs text-emerald-700 font-medium">
              {((freeSlotsCount / 4) * 100).toFixed(0)}% sức chứa trống
            </div>
          </div>

          <div className="bg-white border border-slate-300 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
              <span>XE ĐANG TRONG BÃI</span>
              <span className="text-sky-600 text-base">🚗</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-slate-800 tracking-tight">
                {sessions.length}
              </span>
              <span className="text-xs text-slate-500">phương tiện</span>
            </div>
            <div className="mt-1 text-xs text-sky-700 font-medium">
              1 xe đang đỗ, 1 xe đang vào
            </div>
          </div>

          <div className="bg-white border border-slate-300 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-slate-500 text-xs mb-1">
              <span>LƯỢT XE HÔM NAY</span>
              <span className="text-indigo-600 text-base">📊</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-slate-800 tracking-tight">
                28
              </span>
              <span className="text-xs text-slate-500">lượt</span>
            </div>
            <div className="mt-1 text-xs text-indigo-700 font-medium">
              Vào: 15 | Ra: 13
            </div>
          </div>

          <div className="bg-white border-2 border-amber-400 bg-amber-50/50 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between text-amber-800 text-xs mb-1">
              <span className="font-bold">CHỜ DUYỆT THỦ CÔNG</span>
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-ping"></span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-amber-800 tracking-tight">
                {review && review.status === "PENDING" ? 1 : 0}
              </span>
              <span className="text-xs text-amber-700">yêu cầu</span>
            </div>
            <div className="mt-1 text-xs text-amber-800 font-medium">
              {review && review.status === "PENDING" ? "Cần cán bộ kiểm tra" : "Không có yêu cầu"}
            </div>
          </div>
        </div>

        {/* 2 Column Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left 2 Cols: Sơ đồ 4 Ô đỗ & Bảng phiên xe */}
          <div className="lg:col-span-2 space-y-6">
            <ParkingSlotsGrid slots={slots} />
            <ActiveSessionsTable sessions={sessions} />
          </div>

          {/* Right 1 Col: Manual Review & Realtime Logs */}
          <div className="space-y-6">
            <ManualReviewPanel review={review} onDecision={handleReviewDecision} />
            <RealtimeEventsLog logs={logs} />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-3 text-center text-xs text-slate-500 mt-auto">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Hệ Thống Bãi Đỗ Xe Thông Minh - PBL4</span>
          <span>Phiên bản v1.0.0 | Đồng bộ thời gian thực với Firebase</span>
        </div>
      </footer>
    </div>
  );
};