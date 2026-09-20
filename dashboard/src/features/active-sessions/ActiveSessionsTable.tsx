import React from "react";
import { ParkingSession } from "../../shared/types";

interface ActiveSessionsTableProps {
  sessions: ParkingSession[];
}

export const ActiveSessionsTable: React.FC<ActiveSessionsTableProps> = ({ sessions }) => {
  return (
    <div className="bg-white border border-slate-300 rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-200">
        <div>
          <h2 className="font-extrabold text-base text-[#004b87] uppercase">
            Danh Sách Phương Tiện Trong Bãi
          </h2>
          <p className="text-xs text-slate-500">
            Các phiên xe đã qua cổng và đang đỗ hoặc đang làm thủ tục
          </p>
        </div>
        <span className="text-xs bg-slate-100 border border-slate-300 text-slate-700 px-2.5 py-1 rounded font-semibold">
          Tổng: {sessions.length} xe
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border border-slate-200">
          <thead className="bg-[#e8f0fe] text-[#004b87] font-bold uppercase text-[11px] border-b border-slate-200">
            <tr>
              <th className="py-2.5 px-3 border-r border-slate-200">Mã Phiên</th>
              <th className="py-2.5 px-3 border-r border-slate-200">Biển Số Xe</th>
              <th className="py-2.5 px-3 border-r border-slate-200">Vị Trí Ô</th>
              <th className="py-2.5 px-3 border-r border-slate-200">Thời Gian Vào</th>
              <th className="py-2.5 px-3 border-r border-slate-200">Trạng Thái</th>
              <th className="py-2.5 px-3 text-center">Thao Tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 font-medium">
            {sessions.map((ses) => (
              <tr key={ses.session_id} className="hover:bg-slate-50">
                <td className="py-2.5 px-3 font-mono text-slate-600 border-r border-slate-200">
                  {ses.session_id}
                </td>
                <td className="py-2.5 px-3 border-r border-slate-200 font-bold font-mono text-slate-900">
                  {ses.plate_number}
                </td>
                <td className="py-2.5 px-3 border-r border-slate-200 font-bold text-[#004b87]">
                  {ses.slot_id}
                </td>
                <td className="py-2.5 px-3 border-r border-slate-200 text-slate-600">
                  {ses.entry_time}
                </td>
                <td className="py-2.5 px-3 border-r border-slate-200">
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                      ses.status === "ACTIVE"
                        ? "bg-blue-100 text-blue-800"
                        : "bg-amber-100 text-amber-800"
                    }`}
                  >
                    {ses.status === "ACTIVE" ? "Đang đỗ" : "Đang vào ô"}
                  </span>
                </td>
                <td className="py-2.5 px-3 text-center">
                  <button className="text-[#004b87] hover:underline font-semibold">
                    Xem thẻ
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