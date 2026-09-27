import React from "react";
import { ParkingSlot } from "../types";

interface SlotModalProps {
  isOpen: boolean;
  onClose: () => void;
  slot: ParkingSlot | null;
}

export const SlotModal: React.FC<SlotModalProps> = ({
  isOpen,
  onClose,
  slot,
}) => {
  if (!isOpen || !slot) return null;

  const isFree = slot.status === "FREE";
  const isAssigned = slot.status === "ASSIGNED";
  const isOccupied = slot.status === "OCCUPIED";

  let badgeColor = "bg-emerald-500 text-white";
  if (isOccupied) badgeColor = "bg-[#004b87] text-white";
  if (isAssigned) badgeColor = "bg-amber-400 text-slate-900";

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between pb-3 border-b border-slate-200 mb-4">
          <div className="flex items-center gap-2">
            <span
              className={`font-black text-lg px-2.5 py-0.5 rounded-lg ${badgeColor}`}
            >
              {slot.slot_id}
            </span>
            <span className="font-extrabold text-sm text-[#004b87] uppercase">
              Chi Tiết Vị Trí Ô Đỗ
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 text-lg font-bold cursor-pointer"
          >
            ✕
          </button>
        </div>

        <div className="space-y-3 text-xs">
          {isOccupied && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-slate-800 space-y-1.5">
              <div className="flex justify-between">
                <strong>Trạng thái:</strong>
                <span className="text-[#004b87] font-bold">CÓ XE ĐANG ĐỖ</span>
              </div>
              <div className="flex justify-between">
                <strong>Biển số xe:</strong>
                <span className="font-mono font-bold">{slot.current_plate}</span>
              </div>
              <div className="flex justify-between">
                <strong>Thời gian vào:</strong>
                <span>{slot.entry_time || "Gần đây"}</span>
              </div>
              <div className="flex justify-between">
                <strong>Mô hình phát hiện:</strong>
                <span>ROI IoU 0.88 (Camera Toàn Cảnh)</span>
              </div>
            </div>
          )}

          {isAssigned && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-slate-800 space-y-1.5">
              <div className="flex justify-between">
                <strong>Trạng thái:</strong>
                <span className="text-amber-800 font-bold">ĐÃ GÁN CHO XE</span>
              </div>
              <div className="flex justify-between">
                <strong>Biển số đã cấp:</strong>
                <span className="font-mono font-bold">{slot.current_plate}</span>
              </div>
              <div className="flex justify-between">
                <strong>Thời điểm cấp ô:</strong>
                <span>{slot.entry_time || "Vừa cấp"}</span>
              </div>
              <div className="text-[11px] text-amber-700 mt-2">
                Xe đang trên đường di chuyển từ barie vào vị trí ô {slot.slot_id}.
              </div>
            </div>
          )}

          {isFree && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-slate-800 space-y-1.5">
              <div className="flex justify-between">
                <strong>Trạng thái:</strong>
                <span className="text-emerald-700 font-bold">
                  Ô ĐANG TRỐNG (FREE)
                </span>
              </div>
              <div className="flex justify-between">
                <strong>Sức chứa:</strong>
                <span>1 Ô tô (Tiêu chuẩn)</span>
              </div>
              <div className="flex justify-between">
                <strong>Cảm biến ROI:</strong>
                <span>Hoạt động bình thường</span>
              </div>
              <div className="text-[11px] text-emerald-700 mt-2">
                Sẵn sàng để thuật toán gán cho xe tiếp theo qua cổng vào.
              </div>
            </div>
          )}
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold px-4 py-2 rounded-xl text-xs transition cursor-pointer"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
};
