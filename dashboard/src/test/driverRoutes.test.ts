import { describe, expect, it } from "vitest";
import { DRIVER_ROUTES, evaluateDriverPose } from "../features/user-portal/driverRoutes";

const slotsFromEntrance = ["A1", "A2", "B1", "B2"] as const;

describe("First-Person Driver Navigation 4-Slot Routes (A1, A2, B1, B2)", () => {
  it("places every bay to the left of the aisle in order from the entrance", () => {
    const routes = slotsFromEntrance.map((slotId) => DRIVER_ROUTES[slotId]);
    for (const [index, route] of routes.entries()) {
      const [entrance, turn, destination] = route.radarWaypoints;
      expect(route.turnDirection).toBe("LEFT");
      expect(destination[0]).toBeLessThan(turn[0]);
      expect(turn[0]).toBe(entrance[0]);
      expect(destination[1]).toBe(turn[1]);
      expect(turn[1]).toBeLessThan(index === 0 ? entrance[1] : routes[index - 1].targetBay.cy);
    }
  });

  it("evaluates barrier lift, turn steering, and final parked bay coordinates accurately for all 4 slots", () => {
    slotsFromEntrance.forEach((slotId) => {
      const startPose = evaluateDriverPose(slotId, 0.0);
      expect(startPose.phaseIndex).toBe(0);
      expect(startPose.barrierAngleDeg).toBe(0);
      expect(startPose.barrierIsOpen).toBe(false);

      const midTurnPose = evaluateDriverPose(slotId, 0.7);
      expect(midTurnPose.phaseIndex).toBe(2);
      expect(midTurnPose.barrierIsOpen).toBe(true);
      expect(midTurnPose.turnSignal).toBe("LEFT");
      expect(midTurnPose.steeringAngleDeg).toBeLessThan(0);

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
