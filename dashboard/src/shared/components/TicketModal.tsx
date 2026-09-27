import React from "react";

interface TicketModalProps {
  isOpen: boolean;
  onClose: () => void;
  ticketData: {
    sessionId: string;
    plateNumber: string;
    slotId: string;
    entryTime: string;
    duration?: string;
  } | null;
}

export const TicketModal: React.FC<TicketModalProps> = ({
  isOpen,
  onClose,
  ticketData,
}) => {
  if (!isOpen || !ticketData) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl max-w-sm w-full p-6 shadow-2xl border border-slate-200 animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between pb-3 border-b border-slate-200 mb-4">
          <div className="flex items-center gap-2">
            <span className="w-8 h-8 rounded-lg bg-[#004b87] text-white flex items-center justify-center font-black text-xs">
              PBL4
            </span>
            <span className="font-extrabold text-sm text-[#004b87] uppercase">
              Thẻ Gửi Xe Điện Tử
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 text-lg font-bold cursor-pointer"
          >
            ✕
          </button>
        </div>

        <div className="bg-slate-50 rounded-xl p-4 border border-dashed border-slate-300 text-center space-y-3">
          {/* QR Code Simulation */}
          <div className="w-32 h-32 mx-auto bg-white p-2 rounded-lg border border-slate-300 shadow-xs flex flex-col items-center justify-center">
            <div className="w-24 h-24 bg-slate-900 rounded flex items-center justify-center text-white font-mono text-[10px] text-center p-1">
              [ QR TOKEN VERIFIED ]
            </div>
          </div>

          <div>
            <div className="text-[11px] text-slate-500 font-bold uppercase">
              Biển Số Xe
            </div>
            <div className="text-xl font-black font-mono text-slate-900">
              {ticketData.plateNumber}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs border-t border-slate-200 pt-3 text-left">
            <div>
              <span className="text-slate-500 block text-[10px]">Vị trí đỗ:</span>
              <span className="font-extrabold text-[#004b87] text-sm">
                {ticketData.slotId}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px]">Giờ vào:</span>
              <span className="font-bold text-slate-800">
                {ticketData.entryTime}
              </span>
            </div>
          </div>

          <div className="text-[10px] text-slate-400 font-mono">
            Mã phiên: {ticketData.sessionId}
          </div>
        </div>

        <div className="mt-4 flex justify-end">
          <button
            onClick={onClose}
            className="w-full bg-[#004b87] hover:bg-[#003366] text-white font-bold py-2 rounded-xl text-xs transition cursor-pointer"
          >
            Đóng Cửa Sổ
          </button>
        </div>
      </div>
    </div>
  );
};
