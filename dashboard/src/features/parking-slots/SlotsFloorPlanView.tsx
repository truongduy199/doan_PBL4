import React from "react";
import { ParkingSlot } from "../../shared/types";

interface SlotsFloorPlanViewProps {
  slots: ParkingSlot[];
  onSelectSlot: (slot: ParkingSlot) => void;
}

export const SlotsFloorPlanView: React.FC<SlotsFloorPlanViewProps> = ({
  slots,
  onSelectSlot,
}) => {
  const getSlot = (id: string) => slots.find((s) => s.slot_id === id);

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-2">
        <div>
          <h2 className="text-lg font-black text-[#004b87] uppercase">
            Mặt Bằng Bãi Đỗ & Vùng ROI Camera Toàn Cảnh
          </h2>
          <p className="text-xs text-slate-500">
            Giám sát tọa độ ranh giới nhận diện và cảm biến chiếm dụng 4 vị trí A1 - B2
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="bg-emerald-100 text-emerald-800 text-xs font-bold px-3 py-1 rounded-full border border-emerald-300">
            Camera Index #2: 1920x1080 @15fps
          </span>
        </div>
      </div>

      {/* 2D Simulation Board */}
      <div className="bg-slate-900 rounded-2xl p-6 border-2 border-slate-800 relative overflow-hidden text-white shadow-xl">
        <div className="text-center font-bold text-xs uppercase tracking-widest text-slate-400 mb-4">
          — Lối Vào Xe (Gate In) ➔ Khu Vực Đỗ Xe Trung Tâm ➔ Lối Ra Xe (Gate Out) —
        </div>

        <div className="grid grid-cols-2 gap-6 max-w-3xl mx-auto my-4">
          {/* Row A */}
          {["A1", "A2", "B1", "B2"].map((id) => {
            const slot = getSlot(id);
            const isOccupied = slot?.status === "OCCUPIED";
            const isAssigned = slot?.status === "ASSIGNED";
            const isFree = slot?.status === "FREE";

            let border = "border-emerald-500 bg-emerald-950/30 text-emerald-400";
            let icon = "🅿️";
            let sub = "Trống (FREE)";

            if (isOccupied) {
              border = "border-blue-500 bg-blue-950/40 text-blue-400";
              icon = "🚙";
              sub = `Có xe: ${slot?.current_plate || ""}`;
            } else if (isAssigned) {
              border = "border-amber-400 bg-amber-950/40 text-amber-400";
              icon = "⏳";
              sub = `Đã cấp: ${slot?.current_plate || ""}`;
            }

            return (
              <div
                key={id}
                onClick={() => slot && onSelectSlot(slot)}
                className={`border-2 ${border} rounded-2xl p-4 flex items-center justify-between cursor-pointer hover:scale-105 transition`}
              >
                <div>
                  <span className="text-2xl font-black">{id}</span>
                  <div className="text-xs text-slate-300 mt-1">
                    ROI: [{id === "A1" ? "120, 80, 480, 360" : id === "A2" ? "520, 80, 880, 360" : id === "B1" ? "120, 420, 480, 720" : "520, 420, 880, 720"}]
                  </div>
                  <div className="text-xs font-bold mt-1 font-mono">{sub}</div>
                </div>
                <div className="text-4xl">{icon}</div>
              </div>
            );
          })}
        </div>

        <div className="text-center text-xs text-slate-400 mt-4 border-t border-slate-800 pt-3">
          Hệ số tin cậy chiếm dụng trung bình: <strong className="text-emerald-400">98.8%</strong> | Ngưỡng phân định: IoU &gt; 0.45
        </div>
      </div>
    </div>
  );
};
