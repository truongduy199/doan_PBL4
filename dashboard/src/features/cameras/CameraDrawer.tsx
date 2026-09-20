import React from "react";

interface CameraDrawerProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  cameraStatusText: string;
}

export const CameraDrawer: React.FC<CameraDrawerProps> = ({
  isOpen,
  setIsOpen,
  cameraStatusText,
}) => {
  return (
    <div className="fixed left-0 top-1/4 z-50 flex items-start transition-all duration-300">
      {/* Nút chữ nhật nằm dọc sát mép lề trái có mũi tên tam giác tù */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        title={isOpen ? "Thu gọn camera giám sát" : "Mở 3 camera giám sát (Toàn cảnh, Mặt, Biển số)"}
        className="bg-[#004b87] hover:bg-[#003870] text-white shadow-2xl border-y border-r border-[#003366] rounded-r-lg px-2 py-6 flex flex-col items-center justify-center gap-2 transition cursor-pointer select-none"
      >
        {/* Biểu tượng mũi tên hình tam giác tù */}
        <span
          className={`text-amber-300 text-base font-black transition-transform duration-300 ${
            isOpen ? "rotate-180" : ""
          }`}
        >
          ▶
        </span>
        <span
          className="text-[11px] font-bold uppercase tracking-widest text-slate-100"
          style={{ writingMode: "vertical-rl", textOrientation: "mixed" }}
        >
          CAMERA
        </span>
      </button>

      {/* Drawer trượt mở ra chứa 3 ô camera */}
      {isOpen && (
        <div className="bg-white border-2 border-[#004b87] rounded-r-2xl shadow-2xl p-4 w-[880px] max-w-[92vw] overflow-x-auto ml-0">
          {/* Header Drawer */}
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-200">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-red-600 animate-ping"></span>
              <h3 className="font-extrabold text-sm text-[#004b87] uppercase">
                Hệ Thống 3 Camera Giám Sát Cổng & Ô Đỗ
              </h3>
              <span className="text-[11px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-300 font-medium">
                {cameraStatusText}
              </span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-xs text-slate-500 hover:text-red-600 font-bold px-2 py-1 bg-slate-100 rounded hover:bg-red-50 transition"
            >
              ✕ Thu gọn lại
            </button>
          </div>

          {/* 3 Ô Camera theo thứ tự từ trái qua phải */}
          <div className="flex flex-col lg:flex-row items-center gap-4 justify-between">
            {/* 1. Camera Toàn Cảnh (Hình chữ nhật 16:9, thiết bị camera HD) */}
            <div className="flex-1 w-full flex flex-col items-center">
              <div className="w-full flex items-center justify-between text-xs font-bold text-slate-700 mb-1.5 px-1">
                <span>1. Camera Toàn Cảnh Ô Đỗ</span>
                <span className="text-[10px] bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-mono">
                  HD 16:9
                </span>
              </div>

              <div className="w-full aspect-video bg-slate-900 rounded-lg border-2 border-slate-300 relative flex flex-col items-center justify-center text-white overflow-hidden shadow-inner">
                <div className="text-3xl mb-1 opacity-70">📹</div>
                <div className="text-xs font-semibold text-slate-300">
                  Toàn Cảnh 4 Ô (A1 - B2)
                </div>
                <div className="text-[10px] text-slate-400 mt-1 font-mono">
                  Camera RTSP / USB Index #2
                </div>

                <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/60 px-2 py-0.5 rounded text-[10px] font-bold text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  LIVE
                </div>
                <div className="absolute bottom-2 right-2 text-[10px] bg-black/60 px-1.5 py-0.5 rounded text-slate-300 font-mono">
                  1920x1080 @15fps
                </div>
              </div>
              <div className="text-[11px] text-slate-500 mt-1 text-center">
                Giám sát và phát hiện ô trống/có xe theo ROI
              </div>
            </div>

            {/* 2. Camera Khuôn Mặt (Hình vuông 1:1) */}
            <div className="w-52 flex flex-col items-center">
              <div className="w-full flex items-center justify-between text-xs font-bold text-slate-700 mb-1.5 px-1">
                <span>2. Camera Mặt Tài Xế</span>
                <span className="text-[10px] bg-purple-100 text-purple-800 px-1.5 py-0.5 rounded font-mono">
                  1:1 Vuông
                </span>
              </div>

              <div className="w-52 h-52 bg-slate-900 rounded-lg border-2 border-slate-300 relative flex flex-col items-center justify-center text-white overflow-hidden shadow-inner">
                <div className="text-3xl mb-1 opacity-70">👤</div>
                <div className="text-xs font-semibold text-slate-300">
                  Nhận Diện Khuôn Mặt
                </div>
                <div className="text-[10px] text-slate-400 mt-1 font-mono">
                  InsightFace Buffalo_L
                </div>

                <div className="absolute inset-4 border border-dashed border-cyan-400/50 rounded-full pointer-events-none"></div>

                <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/60 px-2 py-0.5 rounded text-[10px] font-bold text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                  1:1
                </div>
              </div>
              <div className="text-[11px] text-slate-500 mt-1 text-center">
                Trích xuất Face Embedding trong RAM
              </div>
            </div>

            {/* 3. Camera Biển Số Tại Cổng (Hình vuông 1:1) */}
            <div className="w-52 flex flex-col items-center">
              <div className="w-full flex items-center justify-between text-xs font-bold text-slate-700 mb-1.5 px-1">
                <span>3. Camera Biển Số Cổng</span>
                <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-mono">
                  1:1 Vuông
                </span>
              </div>

              <div className="w-52 h-52 bg-slate-900 rounded-lg border-2 border-slate-300 relative flex flex-col items-center justify-center text-white overflow-hidden shadow-inner">
                <div className="text-3xl mb-1 opacity-70">🚗</div>
                <div className="text-xs font-semibold text-slate-300">
                  Chụp Biển Số Xe
                </div>
                <div className="text-[10px] text-slate-400 mt-1 font-mono">
                  YOLO + OCR Model
                </div>

                <div className="absolute bottom-4 bg-white text-black font-mono font-black text-xs px-2.5 py-1 rounded border border-slate-400 shadow">
                  43A - 123.45
                </div>

                <div className="absolute top-2 left-2 flex items-center gap-1.5 bg-black/60 px-2 py-0.5 rounded text-[10px] font-bold text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                  1:1
                </div>
              </div>
              <div className="text-[11px] text-slate-500 mt-1 text-center">
                Nhận diện biển số khi xe kích hoạt cảm biến
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};