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
    <header className="bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col md:flex-row items-center justify-between gap-4">
        {/* System Title */}
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 bg-[#004b87] rounded-lg flex flex-col items-center justify-center text-white shadow-sm border border-[#003366]">
            <span className="font-black text-base tracking-wider leading-none">PBL4</span>
            <span className="text-[9px] uppercase tracking-tight opacity-90">PARKING</span>
          </div>
          <div>
            <h1 className="text-lg md:text-xl font-extrabold text-[#004b87] tracking-tight uppercase">
              Hệ Thống Bãi Đỗ Xe Thông Minh - PBL4
            </h1>
            <div className="text-xs text-slate-500 font-medium">
              Trung tâm Giám sát & Quản trị Vận hành Thời gian thực
            </div>
          </div>
        </div>

        {/* Right Info: Clock & Admin Badge */}
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs font-bold text-slate-800">Cán bộ Quản trị</div>
            <div className="text-[11px] text-slate-500 font-mono">
              Thời gian: <span className="font-semibold text-[#004b87]">{timeStr}</span>
            </div>
          </div>
          <div className="w-10 h-10 rounded-full bg-[#e8f0fe] border border-[#004b87]/30 flex items-center justify-center text-[#004b87] font-bold text-sm shadow-inner">
            AD
          </div>
        </div>
      </div>
    </header>
  );
};