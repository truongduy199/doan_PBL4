import React, { useState } from "react";

export interface HistoryRecord {
  id: string;
  time: string;
  plate: string;
  action: "ENTRY" | "EXIT";
  slot: string;
  faceMatchScore: string;
  result: "SUCCESS" | "REJECTED" | "MANUAL_APPROVED";
}

export const HistoryView: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState("");

  const records: HistoryRecord[] = [
    {
      id: "H1",
      time: "14:42:05",
      plate: "92B-678.90",
      action: "ENTRY",
      slot: "B1",
      faceMatchScore: "Tạo mới Template",
      result: "SUCCESS",
    },
    {
      id: "H2",
      time: "14:20:10",
      plate: "43A-123.45",
      action: "ENTRY",
      slot: "A1",
      faceMatchScore: "Tạo mới Template",
      result: "SUCCESS",
    },
    {
      id: "H3",
      time: "13:50:22",
      plate: "43C-999.88",
      action: "EXIT",
      slot: "A2",
      faceMatchScore: "0.82 (Khớp chuẩn)",
      result: "SUCCESS",
    },
    {
      id: "H4",
      time: "11:15:30",
      plate: "43B-555.12",
      action: "EXIT",
      slot: "B2",
      faceMatchScore: "0.38 (Lệch mặt)",
      result: "REJECTED",
    },
  ];

  const filtered = records.filter((r) =>
    r.plate.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
        <div>
          <h2 className="text-lg font-black text-[#004b87] uppercase">
            Lịch Sử Phương Tiện Vào / Ra Bãi
          </h2>
          <p className="text-xs text-slate-500">
            Nhật ký truy vết thời gian thực phục vụ đối soát và báo cáo PBL4
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Tìm biển số..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="text-xs px-3 py-2 border border-slate-300 rounded-xl focus:outline-none focus:border-[#004b87] w-48 font-mono"
          />
          <button className="bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 text-xs font-bold px-3 py-2 rounded-xl transition cursor-pointer flex items-center gap-1.5">
            <span>📥</span> Xuất File CSV
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-50 text-[#004b87] font-bold uppercase text-[11px] border-b border-slate-200">
            <tr>
              <th className="py-3 px-3.5">Thời Gian</th>
              <th className="py-3 px-3.5">Biển Số Xe</th>
              <th className="py-3 px-3.5">Hành Động</th>
              <th className="py-3 px-3.5 text-center">Vị Trí Ô</th>
              <th className="py-3 px-3.5">Độ Khớp Face</th>
              <th className="py-3 px-3.5">Kết Quả</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 font-medium">
            {filtered.map((item) => (
              <tr key={item.id} className="hover:bg-slate-50">
                <td className="py-3.5 px-3.5 font-mono text-slate-600">
                  {item.time}
                </td>
                <td className="py-3.5 px-3.5 font-mono font-bold text-slate-900">
                  {item.plate}
                </td>
                <td
                  className={`py-3.5 px-3.5 font-bold ${
                    item.action === "ENTRY"
                      ? "text-emerald-700"
                      : "text-blue-700"
                  }`}
                >
                  {item.action === "ENTRY" ? "VÀO BÃI" : "RA BÃI"}
                </td>
                <td className="py-3.5 px-3.5 text-center">
                  <span className="bg-slate-100 text-slate-800 px-2 py-0.5 rounded font-bold">
                    {item.slot}
                  </span>
                </td>
                <td className="py-3.5 px-3.5 text-slate-600 font-mono">
                  {item.faceMatchScore}
                </td>
                <td className="py-3.5 px-3.5">
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      item.result === "SUCCESS"
                        ? "bg-emerald-100 text-emerald-800"
                        : "bg-red-100 text-red-800"
                    }`}
                  >
                    {item.result === "SUCCESS" ? "Thành Công" : "Từ Chối"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
