import React from "react";

interface CameraDrawerProps {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  cameraStatusText: string;
  onSimulateCapture?: () => void;
}

export const CameraDrawer: React.FC<CameraDrawerProps> = ({
  isOpen,
  setIsOpen,
  cameraStatusText,
  onSimulateCapture,
}) => {
  return (
    <div className="fixed left-0 top-32 z-50 flex items-start transition-all duration-300">
      {/* Nút chữ nhật nằm dọc sát mép lề trái có mũi tên tam giác tù */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        title={isOpen ? "Thu gọn camera giám sát" : "Mở 3 camera giám sát (Toàn cảnh, Mặt, Biển số)"}
        className="bg-gradient-to-b from-[#004b87] to-[#002f57] hover:from-[#003870] hover:to-[#002240] text-white shadow-2xl border-y-2 border-r-2 border-amber-400/80 rounded-r-xl px-2.5 py-6 flex flex-col items-center justify-center gap-2.5 transition cursor-pointer select-none group"
      >
        {/* Biểu tượng mũi tên hình tam giác tù */}
        <span
          className={`text-amber-300 text-lg font-black transition-transform duration-300 group-hover:scale-125 ${
            isOpen ? "rotate-180" : ""
          }`}
        >
          ▶
        </span>
        <span
          className="text-[11px] font-black uppercase tracking-widest text-slate-100"
          style={{ writingMode: "vertical-rl", textOrientation: "mixed" }}
        >
          3 CAMERAS
        </span>
        <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping"></span>
      </button>

      {/* Drawer trượt mở ra chứa 3 ô camera */}
      {isOpen && (
        <div className="bg-slate-900/95 backdrop-blur-md border-2 border-amber-400/90 rounded-r-2xl shadow-2xl p-4 w-[920px] max-w-[94vw] overflow-x-auto text-white">
          {/* Header Drawer */}
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-700">
            <div className="flex items-center gap-2.5">
              <span className="w-3 h-3 rounded-full bg-red-500 animate-pulse"></span>
              <h3 className="font-extrabold text-sm text-white uppercase tracking-wide flex items-center gap-2">
                Hệ Thống 3 Luồng Camera Edge Server
                <span className="bg-red-500/20 text-red-400 border border-red-500/40 text-[10px] px-2 py-0.5 rounded font-mono font-bold">
                  LIVE RTSP
                </span>
              </h3>
              <span className="text-[11px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700 font-medium">
                {cameraStatusText}
              </span>
            </div>

            <div className="flex items-center gap-2">
              {onSimulateCapture && (
                <button
                  onClick={onSimulateCapture}
                  className="bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold px-2.5 py-1 rounded text-xs transition flex items-center gap-1 cursor-pointer"
                >
                  <span>⚡</span> Chụp Thử Nghiệm
                </button>
              )}
              <button
                onClick={() => setIsOpen(false)}
                className="text-xs text-slate-400 hover:text-white px-2.5 py-1 bg-slate-800 hover:bg-slate-700 rounded transition cursor-pointer font-bold"
              >
                ✕ Thu Gọn
              </button>
            </div>
          </div>

          {/* 3 Ô Camera theo thứ tự từ trái qua phải */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3.5 items-stretch">
            {/* 1. Camera Toàn Cảnh (HD 16:9, chiếm 6 cột) */}
            <div className="lg:col-span-6 bg-slate-950/80 rounded-xl p-2.5 border border-slate-700 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs font-bold text-slate-200 mb-2">
                <span className="flex items-center gap-1.5">
                  <span className="text-blue-400">📹</span> 1. Camera Toàn Cảnh (ROI 4 Ô)
                </span>
                <span className="text-[10px] bg-blue-900/60 text-blue-300 border border-blue-700 px-1.5 py-0.5 rounded font-mono">
                  HD 16:9 @15fps
                </span>
              </div>

              {/* Mockup Stream with Visual Bounding Boxes for A1, A2, B1, B2 */}
              <div className="relative w-full aspect-video bg-gradient-to-b from-slate-900 to-slate-950 rounded-lg border border-slate-700 overflow-hidden flex items-center justify-center p-2 shadow-inner group">
                <div className="absolute inset-0 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:16px_16px] opacity-40"></div>

                {/* 4 ROI Overlays */}
                <div className="relative z-10 grid grid-cols-2 gap-2 w-full h-full p-1 text-[11px] font-mono">
                  {/* ROI A1 */}
                  <div className="border-2 border-blue-400 bg-blue-500/20 rounded flex flex-col justify-between p-1.5 relative">
                    <div className="flex justify-between items-center">
                      <span className="bg-blue-600 text-white font-bold px-1.5 py-0.2 rounded text-[10px]">ROI: A1</span>
                      <span className="text-blue-300 font-bold text-[10px]">OCCUPIED</span>
                    </div>
                    <div className="text-center my-auto">
                      <span className="text-xl">🚙</span>
                      <div className="text-[10px] font-bold text-white bg-black/60 px-1 rounded">43A-123.45</div>
                    </div>
                    <div className="text-[9px] text-blue-200">Conf: 98.4%</div>
                  </div>

                  {/* ROI A2 */}
                  <div className="border-2 border-emerald-400 bg-emerald-500/10 rounded flex flex-col justify-between p-1.5 relative">
                    <div className="flex justify-between items-center">
                      <span className="bg-emerald-600 text-white font-bold px-1.5 py-0.2 rounded text-[10px]">ROI: A2</span>
                      <span className="text-emerald-400 font-bold text-[10px]">FREE</span>
                    </div>
                    <div className="text-center my-auto">
                      <span className="text-emerald-400 text-lg opacity-80">🅿️</span>
                      <div className="text-[9px] text-emerald-300">Trống</div>
                    </div>
                    <div className="text-[9px] text-emerald-300/80">Conf: 99.1%</div>
                  </div>

                  {/* ROI B1 */}
                  <div className="border-2 border-amber-400 bg-amber-500/20 rounded flex flex-col justify-between p-1.5 relative">
                    <div className="flex justify-between items-center">
                      <span className="bg-amber-600 text-white font-bold px-1.5 py-0.2 rounded text-[10px]">ROI: B1</span>
                      <span className="text-amber-300 font-bold text-[10px]">ASSIGNED</span>
                    </div>
                    <div className="text-center my-auto">
                      <span className="text-amber-300 text-base animate-pulse">⏳</span>
                      <div className="text-[10px] font-bold text-amber-200 bg-black/60 px-1 rounded">92B-678.90</div>
                    </div>
                    <div className="text-[9px] text-amber-300">Xe đang vào</div>
                  </div>

                  {/* ROI B2 */}
                  <div className="border-2 border-emerald-400 bg-emerald-500/10 rounded flex flex-col justify-between p-1.5 relative">
                    <div className="flex justify-between items-center">
                      <span className="bg-emerald-600 text-white font-bold px-1.5 py-0.2 rounded text-[10px]">ROI: B2</span>
                      <span className="text-emerald-400 font-bold text-[10px]">FREE</span>
                    </div>
                    <div className="text-center my-auto">
                      <span className="text-emerald-400 text-lg opacity-80">🅿️</span>
                      <div className="text-[9px] text-emerald-300">Trống</div>
                    </div>
                    <div className="text-[9px] text-emerald-300/80">Conf: 99.5%</div>
                  </div>
                </div>

                <div className="absolute top-2 left-2 z-20 flex items-center gap-1.5 bg-black/75 px-2 py-0.5 rounded text-[10px] font-bold text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> CAM #1 • OVERVIEW
                </div>
                <div className="absolute bottom-2 right-2 z-20 text-[10px] bg-black/75 px-1.5 py-0.5 rounded text-slate-300 font-mono">
                  YOLOv8x-ROI • 18ms
                </div>
              </div>
              <div className="text-[11px] text-slate-400 mt-2 text-center">
                Giám sát và phát hiện ô trống/có xe theo ROI
              </div>
            </div>

            {/* 2. Camera Khuôn Mặt (Hình vuông 1:1, 3 cột) */}
            <div className="lg:col-span-3 bg-slate-950/80 rounded-xl p-2.5 border border-slate-700 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs font-bold text-slate-200 mb-2">
                <span className="flex items-center gap-1.5">
                  <span className="text-purple-400">👤</span> 2. Mặt Tài Xế
                </span>
                <span className="text-[10px] bg-purple-900/60 text-purple-300 border border-purple-700 px-1.5 py-0.5 rounded font-mono">
                  1:1 Vuông
                </span>
              </div>

              <div className="relative w-full aspect-square bg-slate-900 rounded-lg border border-slate-700 overflow-hidden flex flex-col items-center justify-center p-2">
                <div className="w-28 h-36 border-2 border-cyan-400/90 rounded-2xl relative flex flex-col items-center justify-center bg-cyan-950/20">
                  <span className="text-4xl text-slate-400/80">👨‍💼</span>
                  <div className="absolute top-10 left-6 w-1.5 h-1.5 rounded-full bg-cyan-300"></div>
                  <div className="absolute top-10 right-6 w-1.5 h-1.5 rounded-full bg-cyan-300"></div>
                  <div className="absolute top-16 w-1.5 h-1.5 rounded-full bg-cyan-300"></div>
                  <div className="absolute bottom-10 w-4 h-1 rounded bg-cyan-300"></div>
                  
                  <div className="absolute -bottom-3 bg-cyan-600 text-slate-950 font-black text-[9px] px-1.5 py-0.5 rounded font-mono">
                    EMBEDDING: 512-D
                  </div>
                </div>

                <div className="absolute top-2 left-2 flex items-center gap-1 bg-black/75 px-1.5 py-0.5 rounded text-[10px] font-bold text-cyan-400 font-mono">
                  <span>●</span> LIVE 1:1
                </div>
                <div className="absolute top-2 right-2 bg-emerald-950/80 border border-emerald-500/40 text-emerald-300 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold">
                  Liveness: 99.2%
                </div>
                <div className="absolute bottom-2 left-2 right-2 text-center text-[10px] bg-black/75 text-slate-300 rounded py-0.5 font-mono">
                  InsightFace Buffalo_L • 42ms
                </div>
              </div>
              <div className="text-[11px] text-slate-400 mt-2 text-center">
                Trích xuất vector trong RAM, không lưu ảnh mặt
              </div>
            </div>

            {/* 3. Camera Biển Số Tại Cổng (Hình vuông 1:1, 3 cột) */}
            <div className="lg:col-span-3 bg-slate-950/80 rounded-xl p-2.5 border border-slate-700 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs font-bold text-slate-200 mb-2">
                <span className="flex items-center gap-1.5">
                  <span className="text-amber-400">🚗</span> 3. Biển Số Cổng
                </span>
                <span className="text-[10px] bg-amber-900/60 text-amber-300 border border-amber-700 px-1.5 py-0.5 rounded font-mono">
                  1:1 Vuông
                </span>
              </div>

              <div className="relative w-full aspect-square bg-slate-900 rounded-lg border border-slate-700 overflow-hidden flex flex-col items-center justify-center p-2">
                <div className="w-full h-full flex flex-col items-center justify-center relative">
                  <span className="text-5xl text-slate-500 mb-2">🚘</span>
                  <div className="border-2 border-amber-400 bg-white text-slate-950 px-3 py-1 rounded shadow-lg font-mono font-black text-xs tracking-wider flex items-center gap-1.5">
                    <span className="text-[9px] text-slate-500">VN</span>
                    <span>43A-123.45</span>
                  </div>
                  <div className="text-[9px] text-amber-300 font-mono mt-1 font-semibold">
                    Confidence: 99.4%
                  </div>
                </div>

                <div className="absolute top-2 left-2 flex items-center gap-1 bg-black/75 px-1.5 py-0.5 rounded text-[10px] font-bold text-amber-400 font-mono">
                  <span>●</span> CỔNG VÀO
                </div>
                <div className="absolute top-2 right-2 bg-blue-950/80 border border-blue-500/40 text-blue-300 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold">
                  OCR: OK
                </div>
                <div className="absolute bottom-2 left-2 right-2 text-center text-[10px] bg-black/75 text-slate-300 rounded py-0.5 font-mono">
                  YOLO Plate + OCR • 35ms
                </div>
              </div>
              <div className="text-[11px] text-slate-400 mt-2 text-center">
                Tự động nhận diện biển số khi xe đến
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};