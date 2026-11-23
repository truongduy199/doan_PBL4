import React, { useEffect, useRef, useState } from "react";
import { PARKING_SLOT_ORDER, SlotId } from "../../shared/types";
import {
  DRIVER_PHASE_CHECKPOINTS,
  DRIVER_ROUTES,
  evaluateDriverPose,
} from "./driverRoutes";

interface FirstPersonDriverModalProps {
  isOpen: boolean;
  onClose: () => void;
  slotId: SlotId;
  plateDisplay: string;
  bookingId: string;
}

const BASE_DURATION_MS = 9600;

const PERSPECTIVE_BAYS = PARKING_SLOT_ORDER.map((id, index) => {
  const bottom = 376 - index * 47;
  const top = bottom - 39;
  const nearEdge = 268 - (bottom - 170) * 0.272;
  const farEdge = 268 - (top - 170) * 0.272;
  const width = 136 - index * 20;
  return {
    id,
    points: `${farEdge - width + 12},${top} ${farEdge},${top} ${nearEdge},${bottom} ${nearEdge - width},${bottom}`,
    cx: (farEdge + nearEdge - width) / 2,
    cy: (top + bottom) / 2,
  };
});

export const FirstPersonDriverModal: React.FC<FirstPersonDriverModalProps> = ({
  isOpen,
  onClose,
  slotId,
  plateDisplay,
  bookingId,
}) => {
  const [progress, setProgress] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [speedMultiplier, setSpeedMultiplier] = useState<1 | 1.5>(1);
  const lastFrameTimeRef = useRef<number | null>(null);
  const rafIdRef = useRef<number | null>(null);
  const dialogRef = useRef<HTMLDivElement | null>(null);

  const route = DRIVER_ROUTES[slotId] || DRIVER_ROUTES.A1;
  const pose = evaluateDriverPose(slotId, progress);
  const target = PERSPECTIVE_BAYS[PARKING_SLOT_ORDER.indexOf(route.slotId)];

  // Reset & start smooth playback whenever modal opens or slot changes
  useEffect(() => {
    if (!isOpen) return;
    setProgress(0);
    setIsPlaying(true);
    lastFrameTimeRef.current = null;
  }, [isOpen, slotId]);

  // Smooth 60fps requestAnimationFrame timeline loop (100% client-side, zero network/hardware calls)
  useEffect(() => {
    if (!isOpen || !isPlaying) {
      lastFrameTimeRef.current = null;
      return;
    }

    const tick = (nowMs: number) => {
      if (lastFrameTimeRef.current === null) {
        lastFrameTimeRef.current = nowMs;
      }
      const deltaMs = Math.min(100, nowMs - lastFrameTimeRef.current);
      lastFrameTimeRef.current = nowMs;

      setProgress((prev) => {
        const next = prev + (deltaMs * speedMultiplier) / BASE_DURATION_MS;
        if (next >= 1) {
          setIsPlaying(false);
          return 1;
        }
        return next;
      });
      rafIdRef.current = window.requestAnimationFrame(tick);
    };

    rafIdRef.current = window.requestAnimationFrame(tick);
    return () => {
      if (rafIdRef.current !== null) {
        window.cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
  }, [isOpen, isPlaying, speedMultiplier]);

  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const controls = Array.from(dialogRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") || []);
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => { window.removeEventListener("keydown", onKeyDown); document.body.style.overflow = oldOverflow; previous?.focus(); };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleReplay = () => {
    setProgress(0);
    setIsPlaying(true);
    lastFrameTimeRef.current = null;
  };

  const handleJumpToCheckpoint = (targetProgress: number) => {
    setIsPlaying(false);
    setProgress(targetProgress);
  };

  const handleTogglePlay = () => {
    if (progress >= 0.995) {
      handleReplay();
    } else {
      setIsPlaying((prev) => !prev);
    }
  };

  const isCompleted = progress >= 0.96;
  const pct = Math.round(progress * 100);

  return (
    <div
      className="driver-modal fixed inset-0 z-50 bg-slate-950/90 backdrop-blur-md flex items-center justify-center p-2 sm:p-4"
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label={`Mô phỏng góc nhìn người lái tới ô ${slotId}`}
    >
      <div className="bg-slate-900 border border-slate-700/90 rounded-lg max-w-5xl w-full max-h-[94vh] overflow-y-auto shadow-2xl flex flex-col text-white">
        {/* Top Modal Header */}
        <div className="bg-slate-950 px-4 py-3 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-3">
            <span className="px-2.5 py-1 rounded-lg bg-amber-400 text-slate-950 font-black text-xs uppercase tracking-wider shadow-xs">
              Mô phỏng đường đi
            </span>
            <div>
              <h3 className="text-sm sm:text-base font-extrabold text-white flex items-center gap-2 flex-wrap">
                <span>Đường đến ô {slotId}</span>
                <span className="text-xs font-mono bg-blue-900/70 text-sky-300 px-2 py-0.5 rounded-md border border-sky-700">
                  Biển số: {plateDisplay}
                </span>
              </h3>
              <p className="text-[11px] text-slate-400">
                {route.zoneLabel} · Mô phỏng lộ trình; cổng thật vẫn do hệ thống xác nhận.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="bg-slate-800 hover:bg-rose-600 text-slate-200 hover:text-white px-3.5 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer border border-slate-700"
          >
            Đóng
          </button>
        </div>

        {/* Windshield First-Person Cockpit Viewport */}
        <div className="relative h-[430px] sm:h-[480px] w-full bg-gradient-to-b from-slate-950 via-slate-900 to-slate-800 overflow-hidden select-none">
          {/* Left & Right Cockpit A-Pillars */}
          <div
            className="absolute inset-y-0 left-0 w-9 sm:w-16 bg-gradient-to-r from-slate-950 via-slate-900/95 to-transparent z-20 pointer-events-none border-r border-slate-800/40"
            style={{ transform: "skewX(-7deg) translateX(-12px)" }}
          />
          <div
            className="absolute inset-y-0 right-0 w-9 sm:w-16 bg-gradient-to-l from-slate-950 via-slate-900/95 to-transparent z-20 pointer-events-none border-l border-slate-800/40"
            style={{ transform: "skewX(7deg) translateX(12px)" }}
          />

          {/* Top Rearview Mirror */}
          <div className="absolute top-2.5 left-1/2 -translate-x-1/2 z-30 flex flex-col items-center">
            <div className="w-48 h-8 bg-slate-950/95 border-2 border-slate-700 rounded-b-2xl shadow-lg flex items-center justify-center gap-2 px-3">
              <span
                className={`w-2 h-2 rounded-full ${
                  isCompleted ? "bg-emerald-400" : "bg-sky-400 animate-ping"
                }`}
              />
              <span className="text-[11px] font-extrabold tracking-wider text-slate-100 uppercase">
                HUD • ĐÍCH: Ô {slotId} ({pct}%)
              </span>
            </div>
          </div>

          {/* Top-Left HUD Navigation Turn-by-Turn Card */}
          <div className="absolute top-4 left-5 sm:left-14 z-30 bg-slate-950/88 border border-sky-500/45 rounded-xl p-3 shadow-2xl max-w-[290px] backdrop-blur-md">
            <div className="flex items-start gap-2.5">
              <div
                className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl font-black flex-shrink-0 shadow ${
                  isCompleted
                    ? "bg-emerald-500 text-slate-950"
                    : pose.phaseIndex === 2
                    ? route.turnDirection === "LEFT"
                      ? "bg-sky-400 text-slate-950"
                      : "bg-amber-400 text-slate-950"
                    : "bg-blue-600 text-white"
                }`}
              >
                {pose.phaseIndex === 0 && (pose.barrierIsOpen ? "🟢" : "🚧")}
                {pose.phaseIndex === 1 && "⬆️"}
                {pose.phaseIndex === 2 && (route.turnDirection === "LEFT" ? "↰" : "↱")}
                {pose.phaseIndex === 3 && "P"}
              </div>
              <div>
                <div className="text-[10px] font-extrabold uppercase tracking-wider text-sky-400">
                  {pose.phaseTitle}
                </div>
                <div className="text-xs font-bold text-white mt-0.5 leading-snug">
                  {pose.hudInstruction}
                </div>
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-300">
              <span>Khoảng cách tới ô {slotId}:</span>
              <span className="font-mono font-black text-emerald-400">
                {pose.remainingMeters} m
              </span>
            </div>
          </div>

          {/* Top-Right Live Animated 2D Floor-Plan Radar */}
          <div className="absolute top-4 right-5 sm:right-14 z-30 bg-slate-950/92 border border-slate-700 rounded-xl p-2.5 shadow-2xl w-44 sm:w-48 backdrop-blur-md">
            <div className="text-[10px] font-bold text-slate-300 uppercase tracking-wider text-center mb-1 flex items-center justify-between px-1">
              <span>Mặt Bằng Sa Bàn</span>
              <span className="text-emerald-400 font-black">Ô {slotId}</span>
            </div>
            <svg
              viewBox="0 0 200 196"
              className="w-full h-28 sm:h-32 bg-slate-900 rounded-lg border border-slate-800"
            >
              {/* Gate OUT label at top */}
              <text
                x="100"
                y="13"
                textAnchor="middle"
                fill="#94a3b8"
                fontSize="8"
                fontWeight="bold"
              >
                ▲ GATE OUT
              </text>

              {/* Central driving aisle */}
              <rect x="80" y="18" width="40" height="162" fill="#1e293b" />
              <line
                x1="100"
                y1="22"
                x2="100"
                y2="178"
                stroke="#475569"
                strokeWidth="1.5"
                strokeDasharray="5,5"
              />

              {PARKING_SLOT_ORDER.map((id) => {
                const { cx, cy } = DRIVER_ROUTES[id].targetBay;
                const isTarget = id === slotId;
                return (
                  <g key={id}>
                    <rect
                      x={cx - 28}
                      y={cy - 14}
                      width="56"
                      height="28"
                      rx="5"
                      fill={isTarget ? "rgba(16, 185, 129, 0.28)" : "#0f172a"}
                      stroke={isTarget ? "#10b981" : "#334155"}
                      strokeWidth={isTarget ? "2.5" : "1.2"}
                    />
                    <text
                      x={cx}
                      y={cy + 4}
                      textAnchor="middle"
                      fill={isTarget ? "#34d399" : "#94a3b8"}
                      fontSize="12"
                      fontWeight="bold"
                    >
                      {id}
                    </text>
                  </g>
                );
              })}

              {/* Gate IN Barrier Indicator at bottom */}
              <rect
                x="76"
                y="170"
                width="48"
                height="8"
                rx="2"
                fill={pose.barrierIsOpen ? "#10b981" : "#f59e0b"}
              />
              <text
                x="100"
                y="191"
                textAnchor="middle"
                fill={pose.barrierIsOpen ? "#34d399" : "#fbbf24"}
                fontSize="8.5"
                fontWeight="bold"
              >
                GATE IN ({pose.barrierIsOpen ? "MỞ" : "CHỜ"})
              </text>

              {/* Glowing Planned Route Path */}
              <polyline
                points={route.radarPathPoints}
                fill="none"
                stroke="#38bdf8"
                strokeWidth="3.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray="6,4"
              />

              {/* Smoothly moving & rotating vehicle marker */}
              <g
                transform={`translate(${pose.radarCarX}, ${pose.radarCarY}) rotate(${pose.radarCarHeadingDeg})`}
              >
                <rect
                  x="-7"
                  y="-11"
                  width="14"
                  height="22"
                  rx="4"
                  fill="#facc15"
                  stroke="#0f172a"
                  strokeWidth="2"
                />
                <polygon points="0,-10 -4,-3 4,-3" fill="#0f172a" />
              </g>
            </svg>
          </div>

          {/* 3D Perspective Windshield Scene (SVG continuously driven by 60fps pose) */}
          <div
            className="w-full h-full flex items-center justify-center"
            style={{
              transform: `scale(${pose.worldScale.toFixed(4)}) translateX(${pose.worldShiftX.toFixed(
                1
              )}px) rotate(${pose.worldRotateDeg.toFixed(2)}deg)`,
              transformOrigin: "50% 58%",
            }}
          >
            <svg viewBox="0 0 800 420" className="w-full h-full">
              <defs>
                <linearGradient id="fpSkyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#020617" />
                  <stop offset="100%" stopColor="#0f172a" />
                </linearGradient>
                <linearGradient id="fpRoadGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#1e293b" />
                  <stop offset="100%" stopColor="#334155" />
                </linearGradient>
                <linearGradient id="fpGlowCarpet" x1="0" y1="1" x2="0" y2="0">
                  <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.9" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.95" />
                </linearGradient>
              </defs>

              {/* Ceiling & Overhead Lights */}
              <rect x="0" y="0" width="800" height="172" fill="url(#fpSkyGrad)" />
              <line x1="150" y1="24" x2="290" y2="24" stroke="#38bdf8" strokeWidth="3" opacity="0.45" />
              <line x1="510" y1="24" x2="650" y2="24" stroke="#38bdf8" strokeWidth="3" opacity="0.45" />

              {/* Overhead Parking Zone Sign */}
              <rect
                x="230"
                y="42"
                width="340"
                height="34"
                rx="6"
                fill="#004b87"
                stroke="#38bdf8"
                strokeWidth="1.5"
              />
              <text
                x="400"
                y="64"
                textAnchor="middle"
                fill="#ffffff"
                fontSize="13.5"
                fontWeight="bold"
              >
                BÃI ĐỖ XE PBL4 • CÁC Ô BÊN TRÁI
              </text>

              {/* Perspective Asphalt Road */}
              <polygon points="200,420 268,170 532,170 800,420" fill="url(#fpRoadGrad)" />

              {PERSPECTIVE_BAYS.map(({ id, points, cx, cy }) => {
                const isTarget = id === slotId;
                return (
                  <g key={id}>
                    <polygon
                      points={points}
                      fill={isTarget ? "rgba(16, 185, 129, 0.42)" : "rgba(15, 23, 42, 0.78)"}
                      stroke={isTarget ? "#34d399" : "#64748b"}
                      strokeWidth={isTarget ? "3.5" : "1.5"}
                    />
                    <text x={cx} y={cy + 5} textAnchor="middle" fill={isTarget ? "#6ee7b7" : "#cbd5e1"} fontSize="16" fontWeight="bold">
                      {id}
                    </text>
                  </g>
                );
              })}

              {/* Animated Scrolling Center Dashed Line */}
              <line
                x1="400"
                y1="174"
                x2="400"
                y2="405"
                stroke="#94a3b8"
                strokeWidth="3.5"
                strokeDasharray="16,14"
                strokeDashoffset={-pose.roadScrollOffset}
              />

              <path
                d={`M 400 398 L 400 ${target.cy} L ${target.cx} ${target.cy}`}
                fill="none"
                stroke="url(#fpGlowCarpet)"
                strokeWidth="11"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity="0.82"
              />

              {/* Gate IN Barrier Assembly (smoothly lifts 0 -> 85 deg and fades as car passes) */}
              {progress < 0.42 && (
                <g
                  style={{
                    opacity: progress > 0.25 ? Math.max(0, 1 - (progress - 0.25) / 0.17) : 1,
                    transform:
                      progress > 0.25
                        ? `scale(${(1 + (progress - 0.25) * 1.4).toFixed(3)}) translateY(${(
                            (progress - 0.25) * 180
                          ).toFixed(1)}px)`
                        : "scale(1)",
                    transformOrigin: "400px 280px",
                  }}
                >
                  {/* Gate Pedestal & Signal Light */}
                  <rect
                    x="208"
                    y="208"
                    width="34"
                    height="118"
                    rx="4"
                    fill="#f59e0b"
                    stroke="#78350f"
                    strokeWidth="2"
                  />
                  <circle
                    cx="225"
                    cy="230"
                    r="8.5"
                    fill={pose.barrierIsOpen ? "#10b981" : "#ef4444"}
                  />
                  {/* Smoothly Rotating Barrier Arm */}
                  <g
                    transform={`rotate(${-pose.barrierAngleDeg} 234 254)`}
                  >
                    <rect
                      x="234"
                      y="246"
                      width="326"
                      height="14"
                      rx="4"
                      fill="#ef4444"
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                    <rect x="275" y="246" width="35" height="14" fill="#ffffff" />
                    <rect x="345" y="246" width="35" height="14" fill="#ffffff" />
                    <rect x="415" y="246" width="35" height="14" fill="#ffffff" />
                    <rect x="485" y="246" width="35" height="14" fill="#ffffff" />
                  </g>
                </g>
              )}

              {/* Wheel-stop bumper & Parked confirmation banner in final phase */}
              {isCompleted && (
                <g>
                  <rect
                    x="245"
                    y="112"
                    width="310"
                    height="68"
                    rx="14"
                    fill="rgba(6, 78, 59, 0.94)"
                    stroke="#34d399"
                    strokeWidth="2.5"
                  />
                  <text
                    x="400"
                    y="142"
                    textAnchor="middle"
                    fill="#a7f3d0"
                    fontSize="13.5"
                    fontWeight="bold"
                  >
                    ✓ ĐÃ ĐỖ XE NGAY NGẮN TRONG Ô {slotId}
                  </text>
                  <text
                    x="400"
                    y="165"
                    textAnchor="middle"
                    fill="#ffffff"
                    fontSize="14.5"
                    fontWeight="bold"
                  >
                    Xe {plateDisplay} • Dừng an toàn (Hộp số P)
                  </text>
                </g>
              )}
            </svg>
          </div>

          {/* Bottom Cockpit Dashboard, Blinking Turn Signals & Smoothly Rotating Steering Wheel */}
          <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-slate-950 via-slate-950/95 to-transparent z-30 flex items-end justify-between px-4 sm:px-14 pb-3 pointer-events-none">
            {/* Left Instrument Cluster: Speed, Gear & Turn Signal Blinkers */}
            <div className="bg-slate-900/95 border border-slate-700 rounded-2xl px-4 py-2.5 shadow-inner flex items-center gap-3.5">
              <div className="flex items-center gap-1.5">
                <span
                  className={`text-lg font-black transition-opacity ${
                    pose.turnSignal === "LEFT"
                      ? "text-emerald-400 animate-pulse opacity-100"
                      : "text-slate-700 opacity-40"
                  }`}
                >
                  ◀
                </span>
                <span
                  className={`text-lg font-black transition-opacity ${
                    pose.turnSignal === "RIGHT"
                      ? "text-emerald-400 animate-pulse opacity-100"
                      : "text-slate-700 opacity-40"
                  }`}
                >
                  ▶
                </span>
              </div>
              <div className="h-8 w-px bg-slate-800" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-bold">
                  Tốc độ
                </div>
                <div className="text-xl sm:text-2xl font-black font-mono text-sky-400">
                  {pose.speedKmh}{" "}
                  <span className="text-[11px] font-normal text-slate-400">
                    km/h
                  </span>
                </div>
              </div>
              <div className="h-8 w-px bg-slate-800" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-bold">
                  Số
                </div>
                <div
                  className={`text-lg font-black ${
                    pose.gear === "P" ? "text-emerald-400" : "text-amber-300"
                  }`}
                >
                  {pose.gear}
                </div>
              </div>
            </div>

            {/* Center Steering Wheel rotating smoothly at 60fps */}
            <div className="flex flex-col items-center -mb-10">
              <div
                className="w-44 h-44 rounded-full border-[12px] border-slate-800 bg-slate-950/45 shadow-2xl flex items-center justify-center relative ring-2 ring-slate-700"
                style={{ transform: `rotate(${pose.steeringAngleDeg}deg)` }}
              >
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 w-4 h-3 bg-amber-400 rounded-xs" />
                <div className="absolute w-full h-3.5 bg-slate-800 top-1/2 -translate-y-1/2" />
                <div className="absolute w-4 h-1/2 bg-slate-800 bottom-0 left-1/2 -translate-x-1/2" />
                <div className="w-16 h-16 rounded-full bg-slate-900 border-2 border-slate-700 flex flex-col items-center justify-center z-10 shadow-md">
                  <span className="text-[10px] font-black text-amber-400 tracking-wider">
                    PBL4
                  </span>
                  <span className="text-[9px] font-bold text-slate-300">
                    {slotId}
                  </span>
                </div>
              </div>
            </div>

            {/* Right Cockpit Infotainment Panel */}
            <div className="hidden sm:flex bg-slate-900/95 border border-slate-700 rounded-2xl px-4 py-2.5 shadow-inner items-center gap-3">
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-bold">
                  Mã Booking
                </div>
                <div className="text-xs font-mono font-bold text-slate-200">
                  {bookingId.slice(0, 8)}...
                </div>
              </div>
              <div className="h-8 w-px bg-slate-800" />
              <div>
                <div className="text-[10px] text-slate-400 uppercase font-bold">
                  Tuyến Đánh Lái
                </div>
                <div className="text-xs font-extrabold text-amber-300">
                  {route.turnDirection === "LEFT" ? "⬅ Rẽ Trái" : "➡ Rẽ Phải"} (
                  {slotId})
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Interactive Scrubber Progress Bar */}
        <div className="bg-slate-950 px-4 pt-3 pb-1 border-t border-slate-800">
          <div className="flex items-center gap-3">
            <span className="text-[11px] font-mono font-bold text-sky-400 w-10">
              {pct}%
            </span>
            <input
              type="range"
              min={0}
              max={100}
              value={pct}
              aria-label="Thanh tua tiến trình mô phỏng lái xe"
              onChange={(e) => {
                setIsPlaying(false);
                setProgress(Number(e.target.value) / 100);
              }}
              className="w-full accent-amber-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
            />
          </div>
        </div>

        {/* Bottom Interactive Playback Controls Bar */}
        <div className="bg-slate-950 px-4 py-3 flex flex-col lg:flex-row items-center justify-between gap-3">
          {/* 4 Clickable Phase Checkpoints */}
          <div className="flex items-center gap-1.5 flex-wrap justify-center">
            {DRIVER_PHASE_CHECKPOINTS.map((cp) => {
              const active = pose.phaseIndex === cp.index;
              const completed = pose.phaseIndex > cp.index || isCompleted;
              return (
                <button
                  key={cp.index}
                  type="button"
                  onClick={() => handleJumpToCheckpoint(cp.targetProgress)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition cursor-pointer border ${
                    active
                      ? "bg-sky-500 text-slate-950 border-sky-400 shadow"
                      : completed
                      ? "bg-emerald-950/70 text-emerald-300 border-emerald-700/60"
                      : "bg-slate-900 text-slate-400 border-slate-800 hover:bg-slate-800"
                  }`}
                >
                  {cp.shortLabel}
                </button>
              );
            })}
          </div>

          {/* Action Buttons: Replay, Play/Pause, Speed, Exit */}
          <div className="flex items-center gap-2 flex-wrap justify-center">
            <button
              type="button"
              onClick={handleReplay}
              className="bg-slate-800 hover:bg-slate-700 text-white font-bold px-3.5 py-2 rounded-xl text-xs transition cursor-pointer border border-slate-700"
            >
              Xem lại
            </button>

            <button
              type="button"
              onClick={handleTogglePlay}
              className="bg-emerald-700 hover:bg-emerald-600 text-white font-semibold px-4 py-2 rounded-xl text-xs transition cursor-pointer shadow"
            >
              {isPlaying
                ? "Tạm dừng"
                : progress >= 0.995
                ? "Phát lại"
                : "Tiếp tục"}
            </button>

            <button
              type="button"
              onClick={() =>
                setSpeedMultiplier((prev) => (prev === 1 ? 1.5 : 1))
              }
              className="bg-slate-800 hover:bg-slate-700 text-sky-300 font-bold px-3 py-2 rounded-xl text-xs transition cursor-pointer border border-slate-700 font-mono"
              title="Đổi tốc độ mô phỏng"
            >
              {speedMultiplier}x
            </button>

            <button
              type="button"
              onClick={onClose}
              className="bg-rose-600 hover:bg-rose-500 text-white font-bold px-4 py-2 rounded-xl text-xs transition cursor-pointer shadow"
            >
              Thoát
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
