import { PARKING_SLOT_ORDER, SlotId } from "../../shared/types";

export interface DriverRouteConfig {
  slotId: SlotId;
  zoneLabel: string;
  turnDirection: "LEFT";
  distanceMeters: number;
  steeringPeakDeg: number;
  hudStage2: string;
  hudStage3: string;
  radarWaypoints: [number, number][];
  radarPathPoints: string;
  targetBay: { cx: number; cy: number };
}

export interface DriverPose {
  phaseIndex: 0 | 1 | 2 | 3;
  phaseTitle: string;
  hudInstruction: string;
  barrierAngleDeg: number;
  barrierIsOpen: boolean;
  speedKmh: number;
  steeringAngleDeg: number;
  turnSignal: "NONE" | "LEFT" | "RIGHT";
  gear: "D" | "P";
  remainingMeters: number;
  radarCarX: number;
  radarCarY: number;
  radarCarHeadingDeg: number;
  roadScrollOffset: number;
  worldScale: number;
  worldShiftX: number;
  worldRotateDeg: number;
}

function makeDriverRoute(slotId: SlotId, index: number): DriverRouteConfig {
  const distanceMeters = 12 + index * 4;
  const targetBay = { cx: 44, cy: 146 - index * 36 };
  const radarWaypoints: [number, number][] = [
    [100, 178],
    [100, targetBay.cy],
    [targetBay.cx, targetBay.cy],
  ];

  return {
    slotId,
    zoneLabel: `Ô thứ ${index + 1} bên trái từ cổng vào`,
    turnDirection: "LEFT",
    distanceMeters,
    steeringPeakDeg: -75,
    hudStage2: `Đi thẳng dọc làn xe đến ngang ô ${slotId} bên trái`,
    hudStage3: `Bật xi-nhan trái và đánh lái vào ô ${slotId}`,
    radarWaypoints,
    radarPathPoints: radarWaypoints.map((point) => point.join(",")).join(" "),
    targetBay,
  };
}

export const DRIVER_ROUTES = Object.fromEntries(
  PARKING_SLOT_ORDER.map((slotId, index) => [slotId, makeDriverRoute(slotId, index)])
) as Record<SlotId, DriverRouteConfig>;

export const DRIVER_PHASE_CHECKPOINTS: {
  index: 0 | 1 | 2 | 3;
  shortLabel: string;
  title: string;
  targetProgress: number;
}[] = [
  {
    index: 0,
    shortLabel: "1. Cổng Vào & Barie",
    title: "Bước 1/4: Dừng tại Gate IN • Nhận diện & Mở Barie",
    targetProgress: 0.02,
  },
  {
    index: 1,
    shortLabel: "2. Trục Chính",
    title: "Bước 2/4: Tiến qua cổng dọc trục đường trung tâm",
    targetProgress: 0.38,
  },
  {
    index: 2,
    shortLabel: "3. Đánh Lái Vào Ô",
    title: "Bước 3/4: Bật xi-nhan & Đánh lái rẽ vào đúng ô đỗ",
    targetProgress: 0.7,
  },
  {
    index: 3,
    shortLabel: "4. Đỗ Hoàn Tất",
    title: "Bước 4/4: Căn thẳng xe vào chính giữa ô • Hoàn tất",
    targetProgress: 1.0,
  },
];

function clamp01(val: number): number {
  return Math.max(0, Math.min(1, val));
}

function smoothStep(t: number): number {
  const c = clamp01(t);
  return c * c * (3 - 2 * c);
}

/**
 * Pure deterministic kinematics function mapping normalized animation progress [0..1]
 * to continuous cockpit pose (barrier angle, steering angle, radar position, speed, HUD).
 */
export function evaluateDriverPose(slotId: SlotId, rawProgress: number): DriverPose {
  const route = DRIVER_ROUTES[slotId] || DRIVER_ROUTES.A1;
  const p = clamp01(rawProgress);
  const [pStart, pTurn, pEnd] = route.radarWaypoints;
  const approachScale = 1.12 + route.distanceMeters / 150;

  // Phase 0: 0.00 -> 0.25 (Gate IN verification & smooth barrier arm lift 0 -> 85 deg)
  if (p < 0.25) {
    const local = p / 0.25;
    const liftT = smoothStep((local - 0.25) / 0.65);
    const barrierAngleDeg = Math.round(liftT * 85);
    const barrierIsOpen = barrierAngleDeg >= 60;
    return {
      phaseIndex: 0,
      phaseTitle: DRIVER_PHASE_CHECKPOINTS[0].title,
      hudInstruction: barrierIsOpen
        ? "Barie cổng vào ĐÃ MỞ HOÀN TOÀN — Bắt đầu tiến xe qua cổng"
        : "Đang quét đối soát Biển số & Khuôn mặt 1:1 tại Gate IN...",
      barrierAngleDeg,
      barrierIsOpen,
      speedKmh: barrierIsOpen ? Math.round(liftT * 6) : 0,
      steeringAngleDeg: 0,
      turnSignal: "NONE",
      gear: "D",
      remainingMeters: route.distanceMeters,
      radarCarX: pStart[0],
      radarCarY: pStart[1],
      radarCarHeadingDeg: 0,
      roadScrollOffset: 0,
      worldScale: 1 + liftT * 0.04,
      worldShiftX: 0,
      worldRotateDeg: 0,
    };
  }

  // Phase 1: 0.25 -> 0.55 (Cruise straight along the aisle to the target bay)
  if (p < 0.55) {
    const local = smoothStep((p - 0.25) / 0.3);
    const carY = pStart[1] + (pTurn[1] - pStart[1]) * local;
    const remM = Math.max(
      3,
      Math.round(route.distanceMeters * (1 - local * 0.72))
    );
    return {
      phaseIndex: 1,
      phaseTitle: DRIVER_PHASE_CHECKPOINTS[1].title,
      hudInstruction: route.hudStage2,
      barrierAngleDeg: 85,
      barrierIsOpen: true,
      speedKmh: Math.round(8 + Math.sin(local * Math.PI) * 7),
      steeringAngleDeg: 0,
      turnSignal: local > 0.72 ? route.turnDirection : "NONE",
      gear: "D",
      remainingMeters: remM,
      radarCarX: pStart[0],
      radarCarY: carY,
      radarCarHeadingDeg: 0,
      roadScrollOffset: (local * route.distanceMeters * 7) % 40,
      worldScale: 1.04 + local * (approachScale - 1.04),
      worldShiftX: 0,
      worldRotateDeg: 0,
    };
  }

  // Phase 2: 0.55 -> 0.85 (Turn steering wheel into A1/A2/B1/B2 bay)
  if (p < 0.85) {
    const local = smoothStep((p - 0.55) / 0.3);
    const steerEnvelope = Math.sin(local * Math.PI);
    const steeringAngleDeg = Math.round(route.steeringPeakDeg * steerEnvelope);
    const carX = pTurn[0] + (pEnd[0] - pTurn[0]) * local;
    const heading = -90 * Math.min(1, local * 1.25);
    const remM = Math.max(1, Math.round(3 * (1 - local)));
    return {
      phaseIndex: 2,
      phaseTitle: DRIVER_PHASE_CHECKPOINTS[2].title,
      hudInstruction: route.hudStage3,
      barrierAngleDeg: 85,
      barrierIsOpen: true,
      speedKmh: Math.max(4, Math.round(9 * (1 - local * 0.45))),
      steeringAngleDeg,
      turnSignal: route.turnDirection,
      gear: "D",
      remainingMeters: remM,
      radarCarX: carX,
      radarCarY: pTurn[1],
      radarCarHeadingDeg: heading,
      roadScrollOffset: (local * 60) % 40,
      worldScale: approachScale + local * 0.14,
      worldShiftX: local * 115,
      worldRotateDeg: steerEnvelope * 3.5,
    };
  }

  // Phase 3: 0.85 -> 1.00 (Straighten wheel, decelerate smoothly to 0 km/h, shift D -> P)
  const local = smoothStep((p - 0.85) / 0.15);
  const isStopped = p >= 0.97;
  return {
    phaseIndex: 3,
    phaseTitle: DRIVER_PHASE_CHECKPOINTS[3].title,
    hudInstruction: `Xe đã đỗ ngay ngắn chính giữa ô ${slotId}. Cảm biến IR_${slotId} ghi nhận vị trí an toàn.`,
    barrierAngleDeg: 85,
    barrierIsOpen: true,
    speedKmh: isStopped ? 0 : Math.round(4 * (1 - local)),
    steeringAngleDeg: 0,
    turnSignal: "NONE",
    gear: isStopped ? "P" : "D",
    remainingMeters: 0,
    radarCarX: pEnd[0],
    radarCarY: pEnd[1],
    radarCarHeadingDeg: -90,
    roadScrollOffset: 0,
    worldScale: approachScale + 0.14 + local * 0.06,
    worldShiftX: 115,
    worldRotateDeg: 0,
  };
}
