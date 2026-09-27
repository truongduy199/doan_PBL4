import React, { useEffect, useState } from "react";

export const Header: React.FC = () => {
  const [timeStr, setTimeStr] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTimeStr(now.toLocaleTimeString("vi-VN"));
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Brand & Institute Info */}
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 bg-gradient-to-br from-[#004b87] to-[#002f57] rounded-xl flex flex-col items-center justify-center text-white shadow-md border border-[#003366] flex-shrink-0">
            <span className="font-extrabold text-base tracking-wider leading-none text-amber-300">PBL4</span>
            <span className="text-[8px] uppercase tracking-tighter opacity-90 mt-0.5 font-bold">DUT • AI</span>
          </div>
          <div>
            <div className="text-[11px] uppercase font-bold tracking-wider text-slate-500 flex items-center gap-2">
              <span>ĐH Bách Khoa - ĐH Đà Nẵng</span>
              <span className="text-slate-300">•</span>
              <span className="text-[#004b87]">Khoa Công Nghệ Thông Tin</span>
            </div>
            <h1 className="text-base md:text-lg font-black text-[#004b87] tracking-tight uppercase flex items-center gap-2">
              Hệ Thống Quản Trị Bãi Đỗ Xe Thông Minh
              <span className="bg-blue-100 text-[#004b87] text-[10px] font-bold px-2 py-0.5 rounded-full border border-blue-200 normal-case hidden sm:inline-block">
                Edge AI + IoT
              </span>
            </h1>
            <div className="text-[11px] text-slate-500 font-medium">
              Trung tâm Giám sát Nhận diện Khuôn mặt (InsightFace) & Biển số xe theo Thời gian thực
            </div>
          </div>
        </div>

        {/* System Health Quick Pills & Admin Profile */}
        <div className="flex items-center gap-3 flex-wrap justify-end">
          <div className="hidden xl:flex items-center gap-2 text-xs">
            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 px-2.5 py-1.5 rounded-lg">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              <span className="font-semibold text-slate-700">Edge Server:</span>
              <span className="text-emerald-700 font-mono font-bold">42ms</span>
            </div>
            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 px-2.5 py-1.5 rounded-lg">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span className="font-semibold text-slate-700">ESP32 (COM3):</span>
              <span className="text-emerald-700 font-bold">Sẵn sàng</span>
            </div>
            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 px-2.5 py-1.5 rounded-lg">
              <span className="w-2 h-2 rounded-full bg-sky-500"></span>
              <span className="font-semibold text-slate-700">Firebase:</span>
              <span className="text-sky-700 font-bold">Đã đồng bộ</span>
            </div>
          </div>

          {/* Admin Profile */}
          <div className="flex items-center gap-2.5 pl-2 border-l border-slate-200">
            <div className="text-right hidden sm:block">
              <div className="text-xs font-bold text-slate-800">Cán bộ Quản trị</div>
              <div className="text-[10px] text-emerald-600 font-semibold flex items-center justify-end gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Trực ban vận hành
              </div>
            </div>
            <div className="w-9 h-9 rounded-xl bg-[#004b87] text-white flex items-center justify-center font-bold text-xs shadow-sm ring-2 ring-blue-100">
              AD
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};