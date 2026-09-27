import React from "react";
import { ParkingSlot } from "../../shared/types";

interface ParkingSlotsGridProps {
  slots: ParkingSlot[];
  onSelectSlot?: (slot: ParkingSlot) => void;
}

export const ParkingSlotsGrid: React.FC<ParkingSlotsGridProps> = ({
  slots,
  onSelectSlot,
}) => {
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
      borderClass = "border-red-500 bg-red-50/50";
      badgeClass = "bg-red-600 text-white";
      badgeText = "SAI Ô";
      icon = "⚠️";
      subText = "Cảnh báo";
    }

    return (
      <div
        key={slot.slot_id}
        onClick={() => onSelectSlot && onSelectSlot(slot)}
        className={`bg-white border-2 ${borderClass} rounded-xl p-3.5 flex flex-col justify-between h-48 shadow-sm hover:shadow-md hover:scale-[1.02] transition cursor-pointer group`}
      >
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <span className="font-black text-xl text-slate-800">
            {slot.slot_id}
          </span>
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${badgeClass}`}
          >
            {badgeText}
          </span>
        </div>

        <div className="my-auto text-center py-2">
          <div className="text-3xl mb-1 group-hover:scale-110 transition">
            {icon}
          </div>
          {slot.current_plate ? (
            <div className="font-mono text-xs font-black text-slate-900 bg-slate-100 py-1 px-2 rounded border border-slate-300 shadow-2xs">
              {slot.current_plate}
            </div>
          ) : (
            <div className="text-xs font-bold text-emerald-700">
              Sẵn sàng nhận xe
            </div>
          )}
        </div>

        <div className="text-[11px] text-slate-500 flex justify-between border-t border-slate-100 pt-2 font-medium">
          <span>Trạng thái:</span>
          <span className="font-bold text-slate-800">{subText}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 mb-4 border-b border-slate-100 gap-2">
        <div>
          <h2 className="font-extrabold text-base text-[#004b87] uppercase flex items-center gap-2">
            <span>Sơ Đồ 4 Vị Trí Ô Đỗ Trực Quan</span>
            <span className="text-xs bg-blue-50 text-[#004b87] font-bold px-2 py-0.5 rounded border border-blue-200 normal-case">
              Khu Vực A & B
            </span>
          </h2>
          <p className="text-xs text-slate-500">
            Giám sát trạng thái chiếm dụng thời gian thực từ Camera Toàn Cảnh (ROI)
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 text-xs font-semibold flex-wrap">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-emerald-500 border border-emerald-600"></span> Trống
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-amber-400 border border-amber-500"></span> Đã gán
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-[#004b87] border border-[#003366]"></span> Có xe
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-red-500 border border-red-600"></span> Sai ô
          </span>
        </div>
      </div>

      {/* Grid 4 Ô Đỗ */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-slate-50/80 rounded-xl border border-slate-200">
        {slots.map(renderSlotCard)}
      </div>

      {/* Detail Bar */}
      <div className="mt-3 text-xs text-slate-600 bg-slate-100/90 p-2.5 rounded-xl border border-slate-200 flex items-center justify-between">
        <span className="flex items-center gap-1.5">
          <span className="text-blue-600">💡</span>
          <span>Bấm vào từng ô đỗ bất kỳ để xem <strong>thông số kỹ thuật & hình ảnh trích xuất</strong>.</span>
        </span>
        <span className="text-[11px] text-[#004b87] font-bold">
          Firebase Realtime: OK
        </span>
      </div>
    </div>
  );
};