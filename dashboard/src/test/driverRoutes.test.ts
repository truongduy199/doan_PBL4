import { describe, expect, it } from "vitest";
import { DRIVER_ROUTES, evaluateDriverPose } from "../features/user-portal/driverRoutes";

describe("First-Person Driver Navigation 4-Slot Routes (A1, A2, B1, B2)", () => {
  it("routes A1 and A2 turn LEFT and RIGHT at Row A (12m, do not pass Row A)", () => {
    expect(DRIVER_ROUTES.A1.row).toBe("A");
    expect(DRIVER_ROUTES.A1.turnDirection).toBe("LEFT");
    expect(DRIVER_ROUTES.A1.passesRowA).toBe(false);
    expect(DRIVER_ROUTES.A1.distanceMeters).toBe(12);
    expect(DRIVER_ROUTES.A1.steeringPeakDeg).toBeLessThan(0);

    expect(DRIVER_ROUTES.A2.row).toBe("A");
    expect(DRIVER_ROUTES.A2.turnDirection).toBe("RIGHT");
    expect(DRIVER_ROUTES.A2.passesRowA).toBe(false);
    expect(DRIVER_ROUTES.A2.distanceMeters).toBe(12);
    expect(DRIVER_ROUTES.A2.steeringPeakDeg).toBeGreaterThan(0);
  });

  it("routes B1 and B2 pass Row A and turn LEFT and RIGHT at Row B (24m)", () => {
    expect(DRIVER_ROUTES.B1.row).toBe("B");
    expect(DRIVER_ROUTES.B1.turnDirection).toBe("LEFT");
    expect(DRIVER_ROUTES.B1.passesRowA).toBe(true);
    expect(DRIVER_ROUTES.B1.distanceMeters).toBe(24);
    expect(DRIVER_ROUTES.B1.steeringPeakDeg).toBeLessThan(0);

    expect(DRIVER_ROUTES.B2.row).toBe("B");
    expect(DRIVER_ROUTES.B2.turnDirection).toBe("RIGHT");
    expect(DRIVER_ROUTES.B2.passesRowA).toBe(true);
    expect(DRIVER_ROUTES.B2.distanceMeters).toBe(24);
    expect(DRIVER_ROUTES.B2.steeringPeakDeg).toBeGreaterThan(0);
  });

  it("evaluates barrier lift, turn steering, and final parked bay coordinates accurately for all 4 slots", () => {
    (["A1", "A2", "B1", "B2"] as const).forEach((slotId) => {
      const startPose = evaluateDriverPose(slotId, 0.0);
      expect(startPose.phaseIndex).toBe(0);
      expect(startPose.barrierAngleDeg).toBe(0);
      expect(startPose.barrierIsOpen).toBe(false);

      const midTurnPose = evaluateDriverPose(slotId, 0.7);
      expect(midTurnPose.phaseIndex).toBe(2);
      expect(midTurnPose.barrierIsOpen).toBe(true);
      expect(midTurnPose.turnSignal).toBe(DRIVER_ROUTES[slotId].turnDirection);
      if (DRIVER_ROUTES[slotId].turnDirection === "LEFT") {
        expect(midTurnPose.steeringAngleDeg).toBeLessThan(0);
      } else {
        expect(midTurnPose.steeringAngleDeg).toBeGreaterThan(0);
      }

      const endPose = evaluateDriverPose(slotId, 1.0);
      expect(endPose.phaseIndex).toBe(3);
      expect(endPose.gear).toBe("P");
      expect(endPose.speedKmh).toBe(0);
      expect(endPose.remainingMeters).toBe(0);
      expect(endPose.radarCarX).toBe(DRIVER_ROUTES[slotId].targetBay.cx);
      expect(endPose.radarCarY).toBe(DRIVER_ROUTES[slotId].targetBay.cy);
    });
  });
});
