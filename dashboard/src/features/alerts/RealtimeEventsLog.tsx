import React from "react";
import { SystemEventLog } from "../../shared/types";

interface RealtimeEventsLogProps {
  logs: SystemEventLog[];
}

export const RealtimeEventsLog: React.FC<RealtimeEventsLogProps> = ({ logs }) => {
  return (
    <div className="bg-white border border-slate-300 rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between pb-2 mb-3 border-b border-slate-200">
        <h2 className="font-extrabold text-sm text-[#004b87] uppercase">
          Nhật Ký Vận Hành Cục Bộ
        </h2>
        <span className="text-[11px] text-slate-500">Thời gian thực</span>
      </div>

      <div className="space-y-2.5 text-xs">
        {logs.map((log) => {
          let bgClass = "bg-slate-50 border-slate-200";
          let titleColor = "text-slate-800";
          let icon = "ℹ️";

          if (log.severity === "warning") {
            bgClass = "bg-amber-50 border-amber-200";
            titleColor = "text-amber-900";
            icon = "⚠️";
          } else if (log.severity === "success") {
            bgClass = "bg-emerald-50 border-emerald-200";
            titleColor = "text-emerald-900";
            icon = "🚪";
          }

          return (
            <div key={log.id} className={`p-2.5 rounded border ${bgClass}`}>
              <div className="flex justify-between font-bold">
                <span className={titleColor}>
                  {icon} {log.title}
                </span>
                <span className="text-[10px] text-slate-500 font-normal">
                  {log.timestamp}
                </span>
              </div>
              <p className="text-slate-600 text-[11px] mt-0.5">{log.description}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};