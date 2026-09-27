import React from "react";
import { ParkingSession } from "../../shared/types";

interface ActiveSessionsTableProps {
  sessions: ParkingSession[];
  onViewTicket?: (session: ParkingSession) => void;
}

export const ActiveSessionsTable: React.FC<ActiveSessionsTableProps> = ({
  sessions,
  onViewTicket,
}) => {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
        <div>
          <h2 className="font-extrabold text-base text-[#004b87] uppercase">
            Phiên Đỗ Xe Đang Hoạt Động
          </h2>
          <p className="text-xs text-slate-500">
            Các phương tiện đã quét mặt/biển số thành công và đang lưu bãi
          </p>
        </div>
        <span className="text-xs bg-slate-100 border border-slate-300 text-slate-700 px-3 py-1 rounded-full font-bold">
          Đang quản lý: {sessions.length} xe
        </span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-[#004b87] font-bold uppercase text-[11px] border-b border-slate-200">
            <tr>
              <th className="py-3 px-3.5">Mã Phiên</th>
              <th className="py-3 px-3.5">Biển Số Xe</th>
              <th className="py-3 px-3.5 text-center">Ô Đỗ</th>
              <th className="py-3 px-3.5">Thời Gian Vào</th>
              <th className="py-3 px-3.5">Trạng Thái</th>
              <th className="py-3 px-3.5 text-center">Thao Tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-medium">
            {sessions.map((ses) => (
              <tr key={ses.session_id} className="hover:bg-blue-50/40 transition">
                <td className="py-3 px-3.5 font-mono text-slate-600">
                  {ses.session_id}
                </td>
                <td className="py-3 px-3.5">
                  <span className="font-mono font-black text-slate-900 bg-slate-100 border border-slate-300 px-2 py-0.5 rounded shadow-2xs">
                    {ses.plate_number}
                  </span>
                </td>
                <td className="py-3 px-3.5 text-center">
                  <span
                    className={`font-extrabold px-2 py-0.5 rounded text-[11px] ${
                      ses.slot_id === "B1"
                        ? "bg-amber-300 text-amber-900"
                        : "bg-[#004b87] text-white"
                    }`}
                  >
                    {ses.slot_id}
                  </span>
                </td>
                <td className="py-3 px-3.5 text-slate-600">
                  {ses.entry_time}
                </td>
                <td className="py-3 px-3.5">
                  <span
                    className={`px-2.5 py-1 rounded-full text-[11px] font-bold ${
                      ses.status === "ACTIVE"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {ses.status === "ACTIVE" ? "Đang đỗ" : "Đang vào ô"}
                  </span>
                </td>
                <td className="py-3 px-3.5 text-center">
                  <button
                    onClick={() => onViewTicket && onViewTicket(ses)}
                    className="text-[#004b87] hover:text-[#003366] font-bold hover:underline cursor-pointer bg-blue-50 px-2.5 py-1 rounded border border-blue-200"
                  >
                    🎫 Xem Thẻ Xe
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};