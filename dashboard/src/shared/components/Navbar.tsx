import React from "react";

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  pendingReviewsCount?: number;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  pendingReviewsCount = 1,
}) => {
  const tabs = [
    { id: "overview", label: "Tổng Quan Hệ Thống", icon: "📊" },
    { id: "slots", label: "Sơ Đồ Ô Đỗ & ROI (4 Ô)", icon: "🅿️" },
    { id: "sessions", label: "Phiên Xe Hoạt Động", icon: "🚗" },
    { id: "review", label: "Duyệt Ngoại Lệ", icon: "🔍", badge: pendingReviewsCount },
    { id: "history", label: "Lịch Sử Vào / Ra", icon: "🕒" },
    { id: "reports", label: "Báo Cáo & AI Benchmark", icon: "📈" },
  ];

  const getBreadcrumbTitle = (id: string) => {
    switch (id) {
      case "slots":
        return "Sơ đồ ô đỗ & Camera ROI";
      case "sessions":
        return "Phiên xe đang hoạt động";
      case "review":
        return "Trung tâm duyệt ngoại lệ";
      case "history":
        return "Lịch sử vào / ra";
      case "reports":
        return "Báo cáo & AI Benchmark";
      default:
        return "Tổng quan hệ thống";
    }
  };

  return (
    <div>
      {/* Horizontal Nav Bar */}
      <nav className="bg-[#004b87] text-white shadow-inner">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-between overflow-x-auto text-xs font-semibold tracking-wide uppercase">
          <div className="flex items-center">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-3 transition whitespace-nowrap cursor-pointer border-b-2 flex items-center gap-1.5 ${
                    isActive
                      ? "bg-[#003366] text-white border-amber-400 font-bold"
                      : "border-transparent hover:bg-[#003870] text-slate-200"
                  }`}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                  {tab.badge !== undefined && tab.badge > 0 && (
                    <span className="ml-1 bg-amber-400 text-slate-950 text-[10px] font-black px-1.5 py-0.2 rounded-full">
                      {tab.badge}
                    </span>
                  )}
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
              ESP32: Sẵn sàng
            </span>
          </div>
        </div>
      </nav>

      {/* Sub-header Breadcrumb Bar */}
      <div className="bg-slate-200/70 border-b border-slate-300 py-1.5 px-4 text-xs text-slate-600">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-1">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Vị trí:</span>
            <span className="text-[#004b87] font-semibold hover:underline cursor-pointer">
              Bãi đỗ xe Trung tâm PBL4
            </span>
            <span>/</span>
            <span className="font-bold text-slate-800">
              {getBreadcrumbTitle(activeTab)}
            </span>
          </div>
          <div className="flex items-center gap-3 text-[11px] text-slate-500">
            <span className="flex items-center gap-1">
              <span className="inline-block w-2 h-2 bg-emerald-500 rounded-full"></span> Barie Vào: <strong>ĐÓNG</strong>
            </span>
            <span className="text-slate-300">|</span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-2 h-2 bg-emerald-500 rounded-full"></span> Barie Ra: <strong>ĐÓNG</strong>
            </span>
            <span className="text-slate-300">|</span>
            <span className="text-slate-600 font-medium">
              Bảo mật Face: <strong>SQLite RAM Only</strong>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};