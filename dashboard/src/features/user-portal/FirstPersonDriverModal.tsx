import React, { useEffect, useState } from "react";
import { SlotId } from "../../shared/types";

interface FirstPersonDriverModalProps {
  isOpen: boolean;
  onClose: () => void;
  slotId: SlotId;
  plateDisplay: string;
  bookingId: string;
}

interface RouteConfig {
  slotId: SlotId;
  zoneLabel: string;
  turnDirection: "LEFT" | "RIGHT";
  turnLabelVi: string;
  distanceMeters: number;
  steeringAngleDeg: number;
  aisleDepthLabel: string;
  hudInstructionStage2: string;
  hudInstructionStage3: string;
  radarPathPoints: string;
  radarTargetCoords: { cx: number; cy: number };
}

const ROUTE_CONFIGS: Record<SlotId, RouteConfig> = {
  A1: {
    slotId: "A1",
    zoneLabel: "Dãy A • Cánh Trái (Gần Cổng Vào)",
    turnDirection: "LEFT",
    turnLabelVi: "Đánh lái RẼ TRÁI 90° vào ô A1",
    distanceMeters: 12,
    steeringAngleDeg: -65,
    aisleDepthLabel: "Trục chính • Điểm rẽ Dãy A (12m)",
    hudInstructionStage2: "Tiến thẳng 12m qua barie vào trục đường chính tới điểm rẽ Dãy A",
    hudInstructionStage3: "Đánh vô lăng sang TRÁI (-65°), rẽ vào khoang đỗ A1 bên trái",
    radarPathPoints: "100,175 100,115 48,115",
    radarTargetCoords: { cx: 48, cy: 115 },
  },
  A2: {
    slotId: "A2",
    zoneLabel: "Dãy A • Cánh Phải (Gần Cổng Vào)",
    turnDirection: "RIGHT",
    turnLabelVi: "Đánh lái RẼ PHẢI 90° vào ô A2",
    distanceMeters: 12,
    steeringAngleDeg: 65,
    aisleDepthLabel: "Trục chính • Điểm rẽ Dãy A (12m)",
    hudInstructionStage2: "Tiến thẳng 12m qua barie vào trục đường chính tới điểm rẽ Dãy A",
    hudInstructionStage3: "Đánh vô lăng sang PHẢI (+65°), rẽ vào khoang đỗ A2 bên phải",
    radarPathPoints: "100,175 100,115 152,115",
    radarTargetCoords: { cx: 152, cy: 115 },
  },
  B1: {
    slotId: "B1",
    zoneLabel: "Dãy B • Cánh Trái (Phía Trong Bãi)",
    turnDirection: "LEFT",
    turnLabelVi: "Tiến qua Dãy A, đánh lái RẼ TRÁI 90° vào ô B1",
    distanceMeters: 24,
    steeringAngleDeg: -65,
    aisleDepthLabel: "Trục chính • Điểm rẽ Dãy B (24m)",
    hudInstructionStage2: "Tiến thẳng 24m qua Dãy A để vào sâu khu vực Dãy B",
    hudInstructionStage3: "Đánh vô lăng sang TRÁI (-65°), rẽ vào khoang đỗ B1 bên trái",
    radarPathPoints: "100,175 100,60 48,60",
    radarTargetCoords: { cx: 48, cy: 60 },
  },
  B2: {
    slotId: "B2",
    zoneLabel: "Dãy B • Cánh Phải (Phía Trong Bãi)",
    turnDirection: "RIGHT",
    turnLabelVi: "Tiến qua Dãy A, đánh lái RẼ PHẢI 90° vào ô B2",
    distanceMeters: 24,
    steeringAngleDeg: 65,
    aisleDepthLabel: "Trục chính • Điểm rẽ Dãy B (24m)",
    hudInstructionStage2: "Tiến thẳng 24m qua Dãy A để vào sâu khu vực Dãy B",
    hudInstructionStage3: "Đánh vô lăng sang PHẢI (+65°), rẽ vào khoang đỗ B2 bên phải",
    radarPathPoints: "100,175 100,60 152,60",
    radarTargetCoords: { cx: 152, cy: 60 },
  },
};

const STAGE_TITLES = [
  "1. Dừng tại Cổng Vào (Gate IN) • Nhận diện & Mở Barie",
  "2. Tiến qua Cổng Vào trục đường chính của bãi đỗ",
  "3. Đánh lái rẽ vào đúng khoang ô đỗ đã đặt",
  "4. Xe vào vị trí đỗ ngay ngắn trong ô • Hoàn tất",
];

export const FirstPersonDriverModal: React.FC<FirstPersonDriverModalProps> = ({
  isOpen,
  onClose,
  slotId,
  plateDisplay,
  bookingId,
}) => {
  // stage: 0 = Gate IN & Barrier Opening, 1 = Main Aisle Cruise, 2 = Turning into Slot, 3 = Parked in Slot
  const [stage, setStage] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [barrierOpen, setBarrierOpen] = useState<boolean>(false);

  const route = ROUTE_CONFIGS[slotId] || ROUTE_CONFIGS.A1;

  // Reset & auto-play when modal opens
  useEffect(() => {
    if (!isOpen) return;
    setStage(0);
    setIsPlaying(true);
    setBarrierOpen(false);
    const openTimer = window.setTimeout(() => setBarrierOpen(true), 600);
    return () => window.clearTimeout(openTimer);
  }, [isOpen, slotId]);

  // Automatic stage progression when isPlaying is true
  useEffect(() => {
    if (!isOpen || !isPlaying) return;

    if (stage === 0) {
      const bTimer = window.setTimeout(() => setBarrierOpen(true), 500);
      const nextTimer = window.setTimeout(() => setStage(1), 2600);
      return () => {
        window.clearTimeout(bTimer);
        window.clearTimeout(nextTimer);
      };
    }

    if (stage < 3) {
      const timer = window.setTimeout(() => {
        setStage((prev) => Math.min(3, prev + 1));
      }, 2600);
      return () => window.clearTimeout(timer);
    } else {
      setIsPlaying(false);
    }
  }, [isOpen, isPlaying, stage]);

  if (!isOpen) return null;

  const handleReplay = () => {
    setBarrierOpen(false);
    setStage(0);
    setIsPlaying(true);
  };

  const handleStepChange = (targetStage: number) => {
    setIsPlaying(false);
    setStage(targetStage);
    setBarrierOpen(true);
  };

  // Compute steering wheel rotation & speed for current stage
  const currentWheelAngle =
    stage === 2 ? route.steeringAngleDeg : stage === 3 ? 0 : 0;
  const currentSpeedKmh =
    stage === 0 ? (barrierOpen ? 5 : 0) : stage === 1 ? 12 : stage === 2 ? 7 : 0;
  const remainingDistMeters =
    stage === 0
      ? route.distanceMeters
      : stage === 1
      ? Math.round(route.distanceMeters * 0.45)
      : stage === 2
      ? 3
      : 0;

  // Perspective camera transform inside windshield
  const worldScale =
    stage === 0 ? 1.0 : stage === 1 ? 1.16 : stage === 2 ? 1.28 : 1.38;
  const worldShiftX =
    stage >= 2
      ? route.turnDirection === "LEFT"
        ? 85
        : -85
      : 0;

  return (
    <div
      className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center p-2 sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Mô phỏng góc nhìn người lái tới ô ${slotId}`}
    >
      <div className="bg-slate-900 border-2 border-slate-700 rounded-2xl max-w-5xl w-full overflow-hidden shadow-2xl flex flex-col text-white">
        {/* Top Modal Header */}
        <div className="bg-slate-950 px-4 py-3 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 rounded-lg bg-amber-400 text-slate-950 font-black text-xs uppercase tracking-wider">
              POV • Góc Nhìn Sau Vô Lăng
            </span>
            <div>
              <h3 className="text-sm sm:text-base font-extrabold text-white flex items-center gap-2">
                <span>Mô Phỏng Lộ Trình Dẫn Đường Vào Ô Đỗ {slotId}</span>
                <span className="text-xs font-mono bg-blue-900/70 text-sky-300 px-2 py-0.5 rounded border border-sky-700">
                  Biển số: {plateDisplay}
                </span>
              </h3>
              <p className="text-[11px] text-slate-400">
                {route.zoneLabel} • Mô phỏng trực quan trên giao diện (Không phát lệnh mở barie phần cứng thật)
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="bg-slate-800 hover:bg-red-600 text-slate-200 hover:text-white px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer border border-slate-700"
          >
            ✕ Thoát mô phỏng
          </button>
        </div>

        {/* Windshield First-Person Cockpit Viewport */}
        <div className="relative h-[430px] sm:h-[470px] w-full bg-gradient-to-b from-slate-950 via-slate-900 to-slate-800 overflow-hidden select-none">
          {/* Left & Right Cockpit A-Pillars */}
          <div
            className="absolute inset-y-0 left-0 w-8 sm:w-14 bg-gradient-to-r from-slate-950 via-slate-900 to-transparent z-20 pointer-events-none border-r border-slate-800/50"
            style={{ transform: "skewX(-6deg) translateX(-10px)" }}
          />
          <div
            className="absolute inset-y-0 right-0 w-8 sm:w-14 bg-gradient-to-l from-slate-950 via-slate-900 to-transparent z-20 pointer-events-none border-l border-slate-800/50"
            style={{ transform: "skewX(6deg) translateX(10px)" }}
          />

          {/* Top Rearview Mirror & HUD Status Pill */}
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 flex flex-col items-center">
            <div className="w-44 h-8 bg-slate-950/90 border-2 border-slate-700 rounded-b-2xl shadow-lg flex items-center justify-center gap-2 px-3">
              <span
                className={`w-2 h-2 rounded-full ${
                  stage === 3 ? "bg-emerald-400" : "bg-sky-400 animate-ping"
                }`}
              />
              <span className="text-[11px] font-bold tracking-wider text-slate-200 uppercase">
                HUD • ĐÍCH: Ô {slotId}
              </span>
            </div>
          </div>

          {/* Top-Left HUD Navigation Turn Box */}
          <div className="absolute top-4 left-6 sm:left-14 z-30 bg-slate-950/85 border border-sky-500/40 rounded-xl p-3 shadow-xl max-w-xs backdrop-blur-md">
            <div className="flex items-center gap-2.5">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl font-black ${
                  stage === 3
                    ? "bg-emerald-500 text-slate-950"
                    : route.turnDirection === "LEFT"
                    ? "bg-sky-500 text-slate-950"
                    : "bg-amber-400 text-slate-950"
                }`}
              >
                {stage === 0
                  ? "⬆️"
                  : stage === 1
                  ? "⬆️"
                  : stage === 2
                  ? route.turnDirection === "LEFT"
                    ? "↰"
                    : "↱"
                  : "🅿️"}
              </div>
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-sky-400">
                  {STAGE_TITLES[stage]}
                </div>
                <div className="text-xs font-extrabold text-white mt-0.5">
                  {stage === 0 &&
                    (barrierOpen
                      ? "Barie Cổng Vào ĐÃ MỞ — Tiến thẳng qua cổng"
                      : "Đang đối soát Biển số & Khuôn mặt 1:1 tại Gate IN...")}
                  {stage === 1 && route.hudInstructionStage2}
                  {stage === 2 && route.hudInstructionStage3}
                  {stage === 3 &&
                    `Đã đỗ hoàn tất vào chính giữa ô ${slotId}! Cảm biến IR_${slotId} ghi nhận vị trí.`}
                </div>
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-300">
              <span>Khoảng cách tới ô {slotId}:</span>
              <span className="font-mono font-bold text-emerald-400">
                {remainingDistMeters} m
              </span>
            </div>
          </div>

          {/* Top-Right 2D Mini Floor-Plan Radar */}
          <div className="absolute top-4 right-6 sm:right-14 z-30 bg-slate-950/90 border border-slate-700 rounded-xl p-2.5 shadow-xl w-44 backdrop-blur-md">
            <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider text-center mb-1">
              Sa Bàn Mặt Bằng (Tuyến {slotId})
            </div>
            <svg viewBox="0 0 200 190" className="w-full h-28 bg-slate-900 rounded-lg border border-slate-800">
              {/* Central driving lane */}
              <rect x="82" y="15" width="36" height="165" fill="#1e293b" />
              <line
                x1="100"
                y1="20"
                x2="100"
                y2="175"
                stroke="#475569"
                strokeWidth="2"
                strokeDasharray="5,5"
              />

              {/* 4 Parking Slots on Radar: B1 (top-left), B2 (top-right), A1 (mid-left), A2 (mid-right) */}
              {(
                [
                  { id: "B1", x: 18, y: 38 },
                  { id: "B2", x: 126, y: 38 },
                  { id: "A1", x: 18, y: 94 },
                  { id: "A2", x: 126, y: 94 },
                ] as const
              ).map((s) => {
                const isTarget = s.id === slotId;
                return (
                  <g key={s.id}>
                    <rect
                      x={s.x}
                      y={s.y}
                      width="56"
                      height="42"
                      rx="5"
                      fill={isTarget ? "rgba(16, 185, 129, 0.25)" : "#0f172a"}
                      stroke={isTarget ? "#10b981" : "#334155"}
                      strokeWidth={isTarget ? "2.5" : "1.5"}
                    />
                    <text
                      x={s.x + 28}
                      y={s.y + 25}
                      textAnchor="middle"
                      fill={isTarget ? "#34d399" : "#94a3b8"}
                      fontSize="13"
                      fontWeight="bold"
                    >
                      {s.id}
                    </text>
                  </g>
                );
              })}

              {/* Gate IN bar at bottom */}
              <rect x="76" y="166" width="48" height="10" rx="2" fill="#f59e0b" />
              <text x="100" y="186" textAnchor="middle" fill="#fbbf24" fontSize="9" fontWeight="bold">
                GATE IN
              </text>

              {/* Highlighted Route Polyline */}
              <polyline
                points={route.radarPathPoints}
                fill="none"
                stroke="#38bdf8"
                strokeWidth="3.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Moving vehicle dot on radar */}
              <circle
                cx={
                  stage === 0
                    ? 100
                    : stage === 1
                    ? 100
                    : stage === 2
                    ? route.turnDirection === "LEFT"
                      ? 74
                      : 126
                    : route.radarTargetCoords.cx
                }
                cy={
                  stage === 0
                    ? 170
                    : stage === 1
                    ? slotId.startsWith("A")
                      ? 125
                      : 85
                    : route.radarTargetCoords.cy
                }
                r="6"
                fill="#facc15"
                stroke="#0f172a"
                strokeWidth="2"
              />
            </svg>
          </div>

          {/* 3D Perspective Windshield Scene (SVG) */}
          <div
            className="w-full h-full flex items-center justify-center transition-transform duration-700 ease-out"
            style={{
              transform: `scale(${worldScale}) translateX(${worldShiftX}px)`,
            }}
          >
            <svg viewBox="0 0 800 420" className="w-full h-full">
              <defs>
                <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#020617" />
                  <stop offset="100%" stopColor="#0f172a" />
                </linearGradient>
                <linearGradient id="roadGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#1e293b" />
                  <stop offset="100%" stopColor="#334155" />
                </linearGradient>
              </defs>

              {/* Ceiling / Background */}
              <rect x="0" y="0" width="800" height="170" fill="url(#skyGrad)" />

              {/* Parking Structure Pillars & Overhead Sign */}
              <rect x="240" y="45" width="320" height="34" rx="6" fill="#004b87" stroke="#38bdf8" strokeWidth="1.5" />
              <text x="400" y="67" textAnchor="middle" fill="#ffffff" fontSize="14" fontWeight="bold">
                BÃI ĐỖ XE THÔNG MINH PBL4 • KHU A (A1-A2) &amp; KHU B (B1-B2)
              </text>

              {/* Perspective Road / Floor */}
              <polygon points="0,420 270,170 530,170 800,420" fill="url(#roadGrad)" />

              {/* Left & Right Parking Bays in Perspective */}
              {/* Far Row B (B1 Left, B2 Right) */}
              <polygon
                points="155,235 255,180 285,205 195,265"
                fill={slotId === "B1" ? "rgba(16, 185, 129, 0.35)" : "rgba(15, 23, 42, 0.7)"}
                stroke={slotId === "B1" ? "#34d399" : "#64748b"}
                strokeWidth={slotId === "B1" ? "3" : "1.5"}
              />
              <text x="225" y="228" textAnchor="middle" fill={slotId === "B1" ? "#6ee7b7" : "#cbd5e1"} fontSize="16" fontWeight="bold">
                B1
              </text>

              <polygon
                points="645,235 545,180 515,205 605,265"
                fill={slotId === "B2" ? "rgba(16, 185, 129, 0.35)" : "rgba(15, 23, 42, 0.7)"}
                stroke={slotId === "B2" ? "#34d399" : "#64748b"}
                strokeWidth={slotId === "B2" ? "3" : "1.5"}
              />
              <text x="575" y="228" textAnchor="middle" fill={slotId === "B2" ? "#6ee7b7" : "#cbd5e1"} fontSize="16" fontWeight="bold">
                B2
              </text>

              {/* Near Row A (A1 Left, A2 Right) */}
              <polygon
                points="55,325 180,250 225,290 110,375"
                fill={slotId === "A1" ? "rgba(16, 185, 129, 0.38)" : "rgba(15, 23, 42, 0.7)"}
                stroke={slotId === "A1" ? "#34d399" : "#64748b"}
                strokeWidth={slotId === "A1" ? "3.5" : "1.5"}
              />
              <text x="145" y="318" textAnchor="middle" fill={slotId === "A1" ? "#6ee7b7" : "#cbd5e1"} fontSize="20" fontWeight="bold">
                A1
              </text>

              <polygon
                points="745,325 620,250 575,290 690,375"
                fill={slotId === "A2" ? "rgba(16, 185, 129, 0.38)" : "rgba(15, 23, 42, 0.7)"}
                stroke={slotId === "A2" ? "#34d399" : "#64748b"}
                strokeWidth={slotId === "A2" ? "3.5" : "1.5"}
              />
              <text x="655" y="318" textAnchor="middle" fill={slotId === "A2" ? "#6ee7b7" : "#cbd5e1"} fontSize="20" fontWeight="bold">
                A2
              </text>

              {/* Center Aisle Dashed Line */}
              <line
                x1="400"
                y1="175"
                x2="400"
                y2="390"
                stroke="#94a3b8"
                strokeWidth="3"
                strokeDasharray="14,12"
              />

              {/* Glowing AR Ground Carpets guiding into target slot */}
              {slotId === "A1" && (
                <path
                  d="M 400 390 L 400 305 L 155 315"
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity="0.75"
                />
              )}
              {slotId === "A2" && (
                <path
                  d="M 400 390 L 400 305 L 645 315"
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity="0.75"
                />
              )}
              {slotId === "B1" && (
                <path
                  d="M 400 390 L 400 220 L 225 225"
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity="0.75"
                />
              )}
              {slotId === "B2" && (
                <path
                  d="M 400 390 L 400 220 L 575 225"
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity="0.75"
                />
              )}

              {/* Gate IN Barrier Assembly (Visible in Stage 0 & receding in Stage 1) */}
              {stage <= 1 && (
                <g
                  style={{
                    transform: stage === 1 ? "scale(1.22) translateY(35px)" : "scale(1)",
                    transformOrigin: "400px 280px",
                    opacity: stage === 1 ? 0.45 : 1,
                    transition: "all 600ms ease-out",
                  }}
                >
                  {/* Left Gate Pedestal */}
                  <rect x="210" y="210" width="34" height="115" rx="4" fill="#f59e0b" stroke="#78350f" strokeWidth="2" />
                  <circle
                    cx="227"
                    cy="232"
                    r="8"
                    fill={barrierOpen ? "#10b981" : "#ef4444"}
                  />
                  {/* Barrier Arm pivoting from (235, 255) */}
                  <g
                    style={{
                      transform: barrierOpen ? "rotate(-82deg)" : "rotate(0deg)",
                      transformOrigin: "235px 255px",
                      transition: "transform 700ms cubic-bezier(0.34, 1.56, 0.64, 1)",
                    }}
                  >
                    <rect x="235" y="247" width="320" height="14" rx="4" fill="#ef4444" stroke="#ffffff" strokeWidth="2" />
                    <rect x="275" y="247" width="35" height="14" fill="#ffffff" />
                    <rect x="345" y="247" width="35" height="14" fill="#ffffff" />
                    <rect x="415" y="247" width="35" height="14" fill="#ffffff" />
                    <rect x="485" y="247" width="35" height="14" fill="#ffffff" />
                  </g>
                </g>
              )}

              {/* Stage 3 Parked Confirmation Banner inside Windshield */}
              {stage === 3 && (
                <g>
                  <rect
                    x="250"
                    y="120"
                    width="300"
                    height="64"
                    rx="14"
                    fill="rgba(6, 78, 59, 0.92)"
                    stroke="#34d399"
                    strokeWidth="2.5"
                  />
                  <text x="400" y="148" textAnchor="middle" fill="#a7f3d0" fontSize="13" fontWeight="bold">
                    ĐÃ ĐỖ XE NGAY NGẮN TRONG Ô {slotId}
                  </text>
                  <text x="400" y="170" textAnchor="middle" fill="#ffffff" fontSize="15" fontWeight="bold">
                    Biển số {plateDisplay} • Giữ chỗ hợp lệ
                  </text>
                </g>
              )}
            </svg>
          </div>

          {/* Bottom Cockpit Dashboard, Instrument Cluster & Animated Steering Wheel */}
          <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-slate-950 via-slate-950/95 to-transparent z-30 flex items-end justify-between px-6 sm:px-16 pb-3 pointer-events-none">
            {/* Left Instrument Cluster: Digital Speedometer & Gear */}
            <div className="bg-slate-900/95 border border-slate-700 rounded-2xl px-4 py-2.5 shadow-inner flex items-center gap-4">
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-bold">Tốc độ</div>
                <div className="text-2xl font-black font-mono text-sky-400">
                  {currentSpeedKmh} <span className="text-xs font-normal text-slate-400">km/h</span>
                </div>
              </div>
              <div className="h-8 w-px bg-slate-800" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-bold">Hộp số</div>
                <div className="text-lg font-black text-emerald-400">
                  {stage === 3 ? "P (Đỗ)" : "D (Tiến)"}
                </div>
              </div>
            </div>

            {/* Center Steering Wheel (Rotates smoothly when turning into A1, A2, B1, B2) */}
            <div className="flex flex-col items-center -mb-10">
              <div
                className="w-44 h-44 rounded-full border-[12px] border-slate-800 bg-slate-950/40 shadow-2xl flex items-center justify-center relative transition-transform duration-700 ease-in-out ring-2 ring-slate-700"
                style={{ transform: `rotate(${currentWheelAngle}deg)` }}
              >
                {/* Top center yellow racing marker on steering wheel */}
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 w-4 h-3 bg-amber-400 rounded-xs" />
                {/* Horizontal & Vertical Spokes */}
                <div className="absolute w-full h-3.5 bg-slate-800 top-1/2 -translate-y-1/2" />
                <div className="absolute w-4 h-1/2 bg-slate-800 bottom-0 left-1/2 -translate-x-1/2" />
                {/* Center Horn Hub */}
                <div className="w-16 h-16 rounded-full bg-slate-900 border-2 border-slate-700 flex flex-col items-center justify-center z-10 shadow-md">
                  <span className="text-[10px] font-black text-amber-400 tracking-wider">PBL4</span>
                  <span className="text-[9px] font-bold text-slate-400">{slotId}</span>
                </div>
              </div>
            </div>

            {/* Right Cockpit Infotainment Screen */}
            <div className="hidden sm:flex bg-slate-900/95 border border-slate-700 rounded-2xl px-4 py-2.5 shadow-inner items-center gap-3">
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-bold">Mã Booking</div>
                <div className="text-xs font-mono font-bold text-slate-200">
                  {bookingId.slice(0, 8)}...
                </div>
              </div>
              <div className="h-8 w-px bg-slate-800" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-bold">Hướng Đánh Lái</div>
                <div className="text-xs font-extrabold text-amber-300">
                  {route.turnDirection === "LEFT" ? "⬅ Rẽ Trái" : "➡ Rẽ Phải"} ({slotId})
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Interactive Playback Controls Bar */}
        <div className="bg-slate-950 px-4 py-3.5 border-t border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-3">
          {/* 4 Stage Step Pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {[0, 1, 2, 3].map((idx) => {
              const active = stage === idx;
              const completed = stage > idx;
              return (
                <button
                  key={idx}
                  onClick={() => handleStepChange(idx)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer flex items-center gap-1.5 border ${
                    active
                      ? "bg-sky-500 text-slate-950 border-sky-400 shadow"
                      : completed
                      ? "bg-emerald-950/70 text-emerald-300 border-emerald-700/60"
                      : "bg-slate-900 text-slate-400 border-slate-800 hover:bg-slate-800"
                  }`}
                >
                  <span>Bước {idx + 1}</span>
                  {idx === 0 && <span>(Cổng Vào)</span>}
                  {idx === 1 && <span>(Trục Chính)</span>}
                  {idx === 2 && <span>(Đánh Lái {slotId})</span>}
                  {idx === 3 && <span>(Vào Ô {slotId})</span>}
                </button>
              );
            })}
          </div>

          {/* Action Buttons: Replay, Play/Pause, Next Step, Exit */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleReplay}
              className="bg-slate-800 hover:bg-slate-700 text-white font-bold px-3.5 py-2 rounded-xl text-xs transition cursor-pointer border border-slate-700"
            >
              🔄 Xem lại từ đầu
            </button>

            <button
              onClick={() => {
                if (stage === 3) {
                  handleReplay();
                } else {
                  setIsPlaying((prev) => !prev);
                }
              }}
              className="bg-amber-400 hover:bg-amber-300 text-slate-950 font-extrabold px-3.5 py-2 rounded-xl text-xs transition cursor-pointer shadow"
            >
              {isPlaying ? "⏸ Tạm dừng" : stage === 3 ? "▶ Phát lại" : "▶ Tiếp tục"}
            </button>

            <button
              onClick={() => handleStepChange((stage + 1) % 4)}
              className="bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold px-3 py-2 rounded-xl text-xs transition cursor-pointer border border-slate-700"
            >
              ⏭ Chuyển bước
            </button>

            <button
              onClick={onClose}
              className="bg-red-600 hover:bg-red-500 text-white font-bold px-4 py-2 rounded-xl text-xs transition cursor-pointer shadow"
            >
              Thoát
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
