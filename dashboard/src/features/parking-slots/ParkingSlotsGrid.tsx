import React, { useState } from "react";
import { ParkingSlot } from "../../shared/types";

interface ParkingSlotsGridProps {
  slots: ParkingSlot[];
}

export const ParkingSlotsGrid: React.FC<ParkingSlotsGridProps> = ({ slots }) => {
  const [selectedSlot, setSelectedSlot] = useState<ParkingSlot | null>(null);

  const renderSlotCard = (slot: ParkingSlot) => {
    const isFree = slot.status === "FREE";
    const isAssigned = slot.status === "ASSIGNED";
    const isOccupied = slot.status === "OCCUPIED";
    const isWrong = slot.status === "WRONG_VEHICLE";

    let borderClass = "border-emerald-500";
    let badgeClass = "bg-emerald-100 text-emerald-800 border-emerald-300";
    let badgeText = "TRỐNG";
    let icon = "🅿️";
    let subText = "Khả dụng";

    if (isAssigned) {
      borderClass = "border-amber-400";
      badgeClass = "bg-amber-100 text-amber-800 border-amber-300";
      badgeText = "ĐÃ GÁN";
      icon = "⏳";
      subText = "Xe đang vào";
    } else if (isOccupied) {
      borderClass = "border-[#004b87]";
      badgeClass = "bg-[#004b87] text-white";
      badgeText = "CÓ XE";
      icon = "🚙";
      subText = "Đang đỗ";
    } else if (isWrong) {
      borderClass = "border-red-500";
      badgeClass = "bg-red-100 text-red-800 border-red-300";
      badgeText = "SAI Ô";
      icon = "⚠️";
      subText = "Cảnh báo";
    }

    return (
      <div
        key={slot.slot_id}
        onClick={() => setSelectedSlot(slot)}
        className={`bg-white border-2 ${borderClass} rounded-lg p-3 flex flex-col justify-between h-44 shadow-sm hover:shadow-md transition cursor-pointer`}
      >
        <div className="flex items-center justify-between border-b border-slate-100 pb-1.5">
          <span className="font-black text-lg text-slate-800">{slot.slot_id}</span>
          <span className={`text-[10px] px-2 py-0.5 rounded font-bold border ${badgeClass}`}>
            {badgeText}
          </span>
        </div>

        <div className="my-auto text-center py-2">
          <div className="text-3xl mb-1">{icon}</div>
          {slot.current_plate ? (
            <div className="font-mono text-xs font-bold text-slate-900 bg-slate-100 py-1 px-1.5 rounded border border-slate-300">
              {slot.current_plate}
            </div>
          ) : (
            <div className="text-xs font-bold text-emerald-700">Sẵn sàng nhận xe</div>
          )}
        </div>

        <div className="text-[11px] text-slate-500 flex justify-between border-t border-slate-100 pt-1.5">
          <span>Trạng thái:</span>
          <span className="font-bold text-slate-700">{subText}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white border border-slate-300 rounded-xl p-5 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-4 border-b border-slate-200 gap-2">
        <div>
          <h2 className="font-extrabold text-base text-[#004b87] uppercase flex items-center gap-2">
            <span>Sơ Đồ Trực Quan 4 Vị Trí Đỗ Xe</span>
            <span className="text-xs bg-[#e8f0fe] text-[#004b87] font-semibold px-2 py-0.5 rounded border border-blue-200 normal-case">
              Khu vực A & B
            </span>
          </h2>
          <p className="text-xs text-slate-500">Giám sát vị trí thời gian thực qua camera toàn cảnh số 1</p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 text-xs font-semibold">
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-emerald-500 border border-emerald-600"></span> Trống (FREE)
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-amber-400 border border-amber-500"></span> Đã gán (ASSIGNED)
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded bg-[#004b87] border border-[#003366]"></span> Có xe (OCCUPIED)
          </span>
        </div>
      </div>

      {/* Grid 4 Ô Đỗ */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
        {slots.map(renderSlotCard)}
      </div>

      {/* Detail Bar */}
      <div className="mt-3 text-xs text-slate-600 bg-slate-100 p-2.5 rounded border border-slate-200 flex items-center justify-between">
        <span>
          {selectedSlot ? (
            <>
              📍 <strong>Ô {selectedSlot.slot_id}</strong>: Trạng thái:{" "}
              <strong>{selectedSlot.status}</strong>
              {selectedSlot.current_plate && (
                <> | Biển số: <strong className="text-[#004b87] font-mono">{selectedSlot.current_plate}</strong></>
              )}
            </>
          ) : (
            "👉 Nhấp chuột vào bất kỳ ô đỗ nào ở trên để xem thông tin phương tiện chi tiết."
          )}
        </span>
        <span className="text-[11px] text-[#004b87] font-semibold">Tự động đồng bộ với Firebase</span>
      </div>
    </div>
  );
};