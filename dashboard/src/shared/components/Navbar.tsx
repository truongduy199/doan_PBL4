import React from "react";

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  const tabs = [
    { id: "overview", label: "Tổng Quan Hệ Thống" },
    { id: "slots", label: "Sơ Đồ Ô Đỗ (4 Ô)" },
    { id: "sessions", label: "Phiên Xe Hoạt Động" },
    { id: "review", label: "Xác Nhận Thủ Công (Review)" },
    { id: "history", label: "Lịch Sử Vào / Ra" },
    { id: "reports", label: "Báo Cáo & Đánh Giá" },
  ];

  return (
    <div>
      {/* Horizontal Nav */}
      <nav className="bg-[#004b87] text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between overflow-x-auto text-xs font-semibold tracking-wide uppercase">
          <div className="flex items-center">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-3 transition whitespace-nowrap cursor-pointer border-b-2 ${
                    isActive
                      ? "bg-[#003366] text-white border-amber-400 font-bold"
                      : "border-transparent hover:bg-[#003870] text-slate-100"
                  }`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Quick System Indicators */}
          <div className="hidden lg:flex items-center gap-2 py-2 pr-2 text-[11px] font-normal normal-case">
            <span className="inline-flex items-center gap-1.5 bg-emerald-700/90 px-2.5 py-1 rounded text-emerald-100 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse"></span>
              Edge: Online
            </span>
            <span className="inline-flex items-center gap-1.5 bg-sky-700/90 px-2.5 py-1 rounded text-sky-100 font-medium">
              ESP32: COM3
            </span>
            <span className="inline-flex items-center gap-1.5 bg-cyan-700/90 px-2.5 py-1 rounded text-cyan-100 font-medium">
              Firebase: Synced
            </span>
          </div>
        </div>
      </nav>

      {/* Breadcrumb Bar */}
      <div className="bg-slate-200/80 border-b border-slate-300 py-1.5 px-4 text-xs text-slate-600">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className="hover:underline cursor-pointer">Trang chủ</span>
            <span>/</span>
            <span className="hover:underline cursor-pointer">Đồ án PBL4</span>
            <span>/</span>
            <span className="font-semibold text-slate-800">Bảng điều khiển giám sát</span>
          </div>
          <div className="text-[11px] text-slate-500">
            Trạng thái vận hành: <span className="text-emerald-700 font-bold">Bình thường</span>
          </div>
        </div>
      </div>
    </div>
  );
};