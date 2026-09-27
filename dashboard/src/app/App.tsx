import React, { useState, useEffect } from "react";
import { Header } from "../shared/components/Header";
import { Navbar } from "../shared/components/Navbar";
import { CameraDrawer } from "../features/cameras/CameraDrawer";
import { ParkingSlotsGrid } from "../features/parking-slots/ParkingSlotsGrid";
import { ActiveSessionsTable } from "../features/active-sessions/ActiveSessionsTable";
import { ManualReviewPanel } from "../features/manual-review/ManualReviewPanel";
import { RealtimeEventsLog } from "../features/alerts/RealtimeEventsLog";
import { SlotsFloorPlanView } from "../features/parking-slots/SlotsFloorPlanView";
import { HistoryView } from "../features/history/HistoryView";
import { ReportsView } from "../features/reports/ReportsView";
import { TicketModal } from "../shared/components/TicketModal";
import { SlotModal } from "../shared/components/SlotModal";
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

  // Modals state
  const [selectedSlotModal, setSelectedSlotModal] = useState<ParkingSlot | null>(null);
  const [ticketModalData, setTicketModalData] = useState<{
    sessionId: string;
    plateNumber: string;
    slotId: string;
    entryTime: string;
    duration?: string;
  } | null>(null);

  const [logs, setLogs] = useState<SystemEventLog[]>([
    {
      id: "1",
      type: "ENTRY",
      title: "Xe vào: 92B-678.90",
      description: "Đã cấp ô đỗ B1. Barie cổng vào mở và đóng an toàn.",
      timestamp: "14:42:05",
      severity: "success",
    },
    {
      id: "2",
      type: "REVIEW",
      title: "Ngoại lệ cổng ra: 43A-123.45",
      description: "Độ khớp mặt 0.58. Đã tạo yêu cầu xác nhận REQ-01.",
      timestamp: "14:41:50",
      severity: "warning",
    },
    {
      id: "3",
      type: "SLOT",
      title: "Cập nhật ô A1: CÓ XE",
      description: "Camera toàn cảnh xác nhận xe đã đỗ đúng vị trí ROI A1.",
      timestamp: "14:20:45",
      severity: "info",
    },
  ]);

  // Subscribe to Firebase Realtime Database
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

  // Demo Simulation 1: Xe tới cổng -> Tự động mở 3 ô camera
  const handleSimulateArrival = () => {
    setIsCameraOpen(true);
    setCameraStatusText("🔴 Đang chụp biển số & mặt tại Cổng Vào...");

    const newLog: SystemEventLog = {
      id: Date.now().toString(),
      type: "TRIGGER",
      title: "Cảm biến cổng vào kích hoạt",
      description: "Phát hiện xe tới cổng. Hệ thống tự động kích hoạt 3 camera quan sát và trích xuất Face Vector 512-D trong RAM.",
      timestamp: new Date().toLocaleTimeString("vi-VN"),
      severity: "info",
    };
    setLogs((prev) => [newLog, ...prev]);
  };

  // Demo Simulation 2: Xe đã đỗ đúng ô -> Tự động thu gọn 3 ô camera
  const handleSimulateParked = () => {
    setIsCameraOpen(false);
    setCameraStatusText("Chế độ chờ");

    // Update Slot B1 to OCCUPIED
    setSlots((prev) =>
      prev.map((s) => (s.slot_id === "B1" ? { ...s, status: "OCCUPIED" } : s))
    );

    const newLog: SystemEventLog = {
      id: Date.now().toString(),
      type: "PARKED",
      title: "Xe 92B-678.90 đã vào ô B1",
      description: "Camera toàn cảnh xác nhận ROI B1 đã có xe. Tự động thu gọn 3 camera vào lề trái.",
      timestamp: new Date().toLocaleTimeString("vi-VN"),
      severity: "success",
    };
    setLogs((prev) => [newLog, ...prev]);
  };

  // Demo Simulation 3: Giả lập đỗ sai ô
  const handleSimulateWrongParking = () => {
    setSlots((prev) =>
      prev.map((s) =>
        s.slot_id === "B2" ? { ...s, status: "WRONG_VEHICLE", current_plate: "XE LẠ / SAI Ô" } : s
      )
    );

    const newLog: SystemEventLog = {
      id: Date.now().toString(),
      type: "WRONG_SLOT",
      title: "CẢNH BÁO: Đỗ sai ô tại B2",
      description: "Camera toàn cảnh phát hiện xe đỗ vào ô B2 chưa được cấp phép!",
      timestamp: new Date().toLocaleTimeString("vi-VN"),
      severity: "warning",
    };
    setLogs((prev) => [newLog, ...prev]);
  };

  const handleResetSimulation = () => {
    setSlots(defaultSlots);
    setSessions(initialSessions);
    setReview(defaultReview);
    setIsCameraOpen(false);
    setCameraStatusText("Chế độ chờ");
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

  const handleOpenTicketModal = (session: ParkingSession) => {
    setTicketModalData({
      sessionId: session.session_id,
      plateNumber: session.plate_number,
      slotId: session.slot_id,
      entryTime: session.entry_time,
      duration: session.status === "ACTIVE" ? "25 phút" : "1 phút",
    });
  };

  const freeSlotsCount = slots.filter((s) => s.status === "FREE").length;
  const pendingReviewsCount = review && review.status === "PENDING" ? 1 : 0;

  return (
    <div className="min-h-screen flex flex-col bg-slate-100 text-slate-800 selection:bg-blue-200">
      {/* Top Institutional Header */}
      <Header />

      {/* Navigation Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        pendingReviewsCount={pendingReviewsCount}
      />

      {/* 3 Camera Drawer (Sát lề trái với mũi tên tam giác tù) */}
      <CameraDrawer
        isOpen={isCameraOpen}
        setIsOpen={setIsCameraOpen}
        cameraStatusText={cameraStatusText}
        onSimulateCapture={handleSimulateArrival}
      />

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 py-5 flex-1 w-full space-y-6">
        {/* Simulation & Demo Lab Banner */}
        <div className="bg-gradient-to-r from-blue-900 to-[#004b87] rounded-2xl p-4 text-white shadow-md flex flex-col lg:flex-row items-center justify-between gap-4 border border-blue-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-400 text-slate-900 flex items-center justify-center font-black text-lg shadow-sm flex-shrink-0">
              ⚡
            </div>
            <div>
              <div className="text-xs font-bold text-amber-300 uppercase tracking-wider">
                Bảng Thử Nghiệm Kịch Bản Vận Hành (Demo Lab)
              </div>
              <div className="text-sm font-semibold text-white">
                Mô phỏng kích hoạt cảm biến vào/ra để kiểm tra luồng camera và cơ chế ra quyết định:
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap justify-end">
            <button
              onClick={handleSimulateArrival}
              className="bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold px-3 py-2 rounded-xl text-xs transition shadow cursor-pointer flex items-center gap-1.5"
            >
              <span>🚗</span> 1. Xe Đến Cổng (Mở Cam)
            </button>
            <button
              onClick={handleSimulateParked}
              className="bg-white/10 hover:bg-white/20 text-white font-bold px-3 py-2 rounded-xl text-xs transition border border-white/20 cursor-pointer flex items-center gap-1.5"
            >
              <span>🅿️</span> 2. Xe Vào Ô B1 (Đóng Cam)
            </button>
            <button
              onClick={handleSimulateWrongParking}
              className="bg-red-500/20 hover:bg-red-500/30 text-red-200 border border-red-400/40 font-bold px-3 py-2 rounded-xl text-xs transition cursor-pointer flex items-center gap-1.5"
            >
              <span>⚠️</span> 3. Giả lập Đỗ Sai Ô
            </button>
            <button
              onClick={handleResetSimulation}
              className="bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold px-2.5 py-2 rounded-xl text-xs transition cursor-pointer"
              title="Khôi phục trạng thái ban đầu"
            >
              🔄 Đặt lại
            </button>
          </div>
        </div>

        {/* Tab 1: OVERVIEW */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* KPI Summary Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm hover:shadow-md transition">
                <div className="flex items-center justify-between text-slate-500 text-xs mb-1.5">
                  <span className="font-bold uppercase tracking-wider">Ô Đỗ Khả Dụng</span>
                  <span className="w-6 h-6 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-xs">
                    🟢
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-[#004b87] tracking-tight">
                    {freeSlotsCount}
                  </span>
                  <span className="text-xs text-slate-400 font-medium">/ 4 vị trí</span>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-emerald-700 font-bold">
                    {((freeSlotsCount / 4) * 100).toFixed(0)}% sức chứa trống
                  </span>
                  <span className="text-slate-400 text-[11px]">Khu vực A & B</span>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm hover:shadow-md transition">
                <div className="flex items-center justify-between text-slate-500 text-xs mb-1.5">
                  <span className="font-bold uppercase tracking-wider">Xe Đang Trong Bãi</span>
                  <span className="w-6 h-6 rounded-lg bg-sky-100 text-sky-700 flex items-center justify-center font-bold text-xs">
                    🚗
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-slate-800 tracking-tight">
                    {sessions.length}
                  </span>
                  <span className="text-xs text-slate-400 font-medium">phương tiện</span>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-sky-700 font-medium">1 xe đang đỗ • 1 xe đang vào</span>
                  <span className="text-slate-400 text-[11px]">Đồng bộ Firebase</span>
                </div>
              </div>

              <div className="bg-white border border-slate-200 rounded-2xl p-4 shadow-sm hover:shadow-md transition">
                <div className="flex items-center justify-between text-slate-500 text-xs mb-1.5">
                  <span className="font-bold uppercase tracking-wider">Lượt Xe Trong Ngày</span>
                  <span className="w-6 h-6 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs">
                    📊
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-slate-800 tracking-tight">
                    28
                  </span>
                  <span className="text-xs text-slate-400 font-medium">lượt xe</span>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-indigo-700 font-medium">Vào: 15 | Ra: 13 xe</span>
                  <span className="text-emerald-600 font-bold text-[11px]">↑ 12% so hôm qua</span>
                </div>
              </div>

              <div className="bg-amber-50/60 border-2 border-amber-400/90 rounded-2xl p-4 shadow-sm hover:shadow-md transition">
                <div className="flex items-center justify-between text-amber-900 text-xs mb-1.5">
                  <span className="font-bold uppercase tracking-wider">Cần Duyệt Thủ Công</span>
                  <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-ping"></span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-amber-800 tracking-tight">
                    {pendingReviewsCount}
                  </span>
                  <span className="text-xs text-amber-700 font-medium">yêu cầu chờ xử lý</span>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-amber-800 font-bold">
                    {pendingReviewsCount > 0 ? "Khớp mặt bất định (0.58)" : "Không có yêu cầu"}
                  </span>
                  {pendingReviewsCount > 0 && (
                    <button
                      onClick={() => setActiveTab("review")}
                      className="text-[11px] font-bold text-[#004b87] hover:underline cursor-pointer"
                    >
                      Xử lý ngay →
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* 2 Column Main Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left 2 Cols: 4 Slots Grid & Active Sessions Table */}
              <div className="lg:col-span-2 space-y-6">
                <ParkingSlotsGrid
                  slots={slots}
                  onSelectSlot={(slot) => setSelectedSlotModal(slot)}
                />
                <ActiveSessionsTable
                  sessions={sessions}
                  onViewTicket={handleOpenTicketModal}
                />
              </div>

              {/* Right 1 Col: Manual Review & Realtime Logs */}
              <div className="space-y-6">
                <ManualReviewPanel
                  review={review}
                  onDecision={handleReviewDecision}
                />
                <RealtimeEventsLog logs={logs} />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: SLOTS & ROI */}
        {activeTab === "slots" && (
          <SlotsFloorPlanView
            slots={slots}
            onSelectSlot={(slot) => setSelectedSlotModal(slot)}
          />
        )}

        {/* Tab 3: SESSIONS */}
        {activeTab === "sessions" && (
          <div className="space-y-6">
            <ActiveSessionsTable
              sessions={sessions}
              onViewTicket={handleOpenTicketModal}
            />
          </div>
        )}

        {/* Tab 4: REVIEW */}
        {activeTab === "review" && (
          <div className="max-w-2xl mx-auto space-y-6">
            <ManualReviewPanel
              review={review}
              onDecision={handleReviewDecision}
            />
          </div>
        )}

        {/* Tab 5: HISTORY */}
        {activeTab === "history" && <HistoryView />}

        {/* Tab 6: REPORTS */}
        {activeTab === "reports" && <ReportsView />}
      </main>

      {/* Ticket Modal */}
      <TicketModal
        isOpen={!!ticketModalData}
        onClose={() => setTicketModalData(null)}
        ticketData={ticketModalData}
      />

      {/* Slot Modal */}
      <SlotModal
        isOpen={!!selectedSlotModal}
        onClose={() => setSelectedSlotModal(null)}
        slot={selectedSlotModal}
      />

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-3 text-center text-xs text-slate-500 mt-auto">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span className="font-semibold text-slate-600">
            Đồ Án PBL4: Bãi Đỗ Xe Thông Minh Nhận Diện Mặt (InsightFace) & Biển Số Xe
          </span>
          <span>Đại học Bách Khoa - ĐH Đà Nẵng © 2026</span>
        </div>
      </footer>
    </div>
  );
};