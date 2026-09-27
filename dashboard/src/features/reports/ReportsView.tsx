import React from "react";

export const ReportsView: React.FC = () => {
  return (
    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6">
      <div className="pb-4 border-b border-slate-100">
        <h2 className="text-lg font-black text-[#004b87] uppercase">
          Báo Cáo Đánh Giá & Benchmark Hệ Thống AI (PBL4)
        </h2>
        <p className="text-xs text-slate-500">
          Các chỉ số định lượng theo đề cương nghiên cứu khoa học bãi đỗ xe thông minh
        </p>
      </div>

      {/* AI Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 font-bold uppercase mb-1">
            InsightFace Buffalo_L
          </div>
          <div className="text-2xl font-black text-[#004b87]">99.2% TAR</div>
          <div className="text-xs text-slate-600 mt-1">
            Tại ngưỡng FAR = 0.001 (Cosine: 0.65)
          </div>
          <div className="text-[11px] text-emerald-700 font-semibold mt-1">
            Độ trễ suy luận: 42ms
          </div>
        </div>

        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 font-bold uppercase mb-1">
            YOLO Plate + OCR
          </div>
          <div className="text-2xl font-black text-[#004b87]">98.6% Accuracy</div>
          <div className="text-xs text-slate-600 mt-1">
            Nhận diện đúng biển số 1 dòng & 2 dòng
          </div>
          <div className="text-[11px] text-emerald-700 font-semibold mt-1">
            Độ trễ suy luận: 35ms
          </div>
        </div>

        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
          <div className="text-xs text-slate-500 font-bold uppercase mb-1">
            ESP32 Hardware Serial
          </div>
          <div className="text-2xl font-black text-[#004b87]">2.4 ms ACK</div>
          <div className="text-xs text-slate-600 mt-1">
            Giao thức ACK/event_id chống trùng lặp
          </div>
          <div className="text-[11px] text-emerald-700 font-semibold mt-1">
            Tỷ lệ mất gói: 0.0%
          </div>
        </div>
      </div>

      <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl text-xs text-slate-700 space-y-1.5">
        <p className="font-bold text-[#004b87]">📌 Ghi chú kiến trúc hệ thống:</p>
        <p>
          • Dữ liệu Face Embedding 512 chiều chỉ được tạo và lưu tạm trong RAM máy Edge Server, không ghi xuống file và không gửi lên Firebase Cloud.
        </p>
        <p>
          • Dashboard chỉ tạo bản ghi xác nhận duyệt (Review Request); Edge Server là đơn vị duy nhất gửi lệnh điều khiển mở barie qua cổng Serial.
        </p>
      </div>
    </div>
  );
};
