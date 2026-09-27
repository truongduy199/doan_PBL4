import React, { useState } from "react";
import { ReviewRequest } from "../../shared/types";

interface ManualReviewPanelProps {
  review: ReviewRequest | null;
  onDecision: (requestId: string, approved: boolean) => void;
}

export const ManualReviewPanel: React.FC<ManualReviewPanelProps> = ({
  review,
  onDecision,
}) => {
  const [resolvedMessage, setResolvedMessage] = useState<string | null>(null);

  if (!review || review.status !== "PENDING") {
    return (
      <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm text-center">
        <div className="text-3xl mb-1 text-emerald-500">✅</div>
        <h3 className="text-sm font-bold text-slate-700">Không có yêu cầu cần duyệt</h3>
        <p className="text-xs text-slate-500 mt-1">
          Hệ thống hoạt động bình thường, không có ngoại lệ khuôn mặt hay sai ô đỗ.
        </p>
      </div>
    );
  }

  const handleAction = (approved: boolean) => {
    onDecision(review.request_id, approved);
    setResolvedMessage(
      approved
        ? `✓ Đã chấp thuận mở barie ra cho xe ${review.plate_number}! Lệnh đã gửi tới Edge Server.`
        : "✕ Đã từ chối xe ra. Barie tiếp tục đóng để kiểm tra bổ sung."
    );
  };

  return (
    <div className="bg-white border-2 border-amber-400 rounded-2xl p-5 shadow-sm">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-amber-200">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-amber-500 animate-ping"></span>
          <h2 className="font-extrabold text-sm text-[#004b87] uppercase tracking-wide">
            Yêu Cầu Xác Nhận Thủ Công
          </h2>
        </div>
        <span className="text-[10px] font-mono bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full font-bold">
          {review.request_id}
        </span>
      </div>

      <p className="text-xs text-slate-600 mb-3.5 leading-relaxed">
        Hệ thống phát hiện độ tương đồng khuôn mặt lúc ra nằm trong <strong>vùng bất định (0.45 - 0.65)</strong>. Cán bộ quản trị cần đối chiếu trực quan.
      </p>

      {/* Face Comparison Visual (Entry vs Exit) */}
      <div className="grid grid-cols-2 gap-2.5 mb-3.5">
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-2 text-center">
          <div className="text-[10px] font-bold text-slate-500 uppercase mb-1">Mặt lúc VÀO</div>
          <div className="w-full aspect-square bg-slate-200 rounded-lg flex flex-col items-center justify-center text-slate-700 relative overflow-hidden">
            <span className="text-3xl">👨‍💼</span>
            <div className="absolute bottom-1 bg-black/60 text-white text-[9px] px-1 rounded font-mono">14:20:10</div>
          </div>
        </div>
        <div className="bg-amber-50/60 border border-amber-200 rounded-xl p-2 text-center">
          <div className="text-[10px] font-bold text-amber-800 uppercase mb-1">Mặt lúc RA</div>
          <div className="w-full aspect-square bg-amber-100 rounded-lg flex flex-col items-center justify-center text-amber-900 relative overflow-hidden border border-amber-300">
            <span className="text-3xl">👨‍💼</span>
            <div className="absolute bottom-1 bg-amber-900 text-white text-[9px] px-1 rounded font-mono">14:45:00</div>
          </div>
        </div>
      </div>

      <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 mb-4 space-y-2.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500">Biển số nhận diện:</span>
          <span className="font-mono font-black text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-300">
            {review.plate_number}
          </span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500">Mã lý do cảnh báo:</span>
          <span className="text-amber-800 font-bold bg-amber-100 px-1.5 py-0.5 rounded">
            {review.reason_code}
          </span>
        </div>

        {/* Cosine Gauge */}
        <div className="space-y-1 pt-1">
          <div className="flex justify-between text-[11px]">
            <span className="text-slate-600 font-medium">Độ khớp Cosine:</span>
            <span className="font-mono font-black text-amber-700 bg-amber-100 px-1.5 py-0.2 rounded">
              {review.similarity_score.toFixed(2)} / 1.00
            </span>
          </div>
          <div className="w-full bg-slate-200 h-3 rounded-full overflow-hidden flex border border-slate-300 shadow-inner">
            <div className="bg-red-400 h-full" style={{ width: "45%" }} title="Từ chối (< 0.45)"></div>
            <div className="bg-amber-400 h-full relative" style={{ width: "20%" }} title="Bất định (0.45 - 0.65)">
              <div className="absolute top-0 bottom-0 left-[65%] w-1 bg-slate-900 shadow"></div>
            </div>
            <div className="bg-emerald-500 h-full" style={{ width: "35%" }} title="Khớp (> 0.65)"></div>
          </div>
          <div className="flex justify-between text-[10px] text-slate-400 font-mono">
            <span>0.0 (Từ chối)</span>
            <span className="text-amber-700 font-bold">0.45 - 0.65</span>
            <span>1.0 (Khớp)</span>
          </div>
        </div>
      </div>

      {resolvedMessage ? (
        <div className="text-center py-2.5 bg-emerald-50 border border-emerald-300 rounded-xl text-xs text-emerald-800 font-bold">
          {resolvedMessage}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => handleAction(false)}
            className="bg-red-50 hover:bg-red-100 text-red-700 border border-red-300 font-bold py-2.5 px-3 rounded-xl text-xs transition cursor-pointer"
          >
            ✕ Từ Chối
          </button>
          <button
            onClick={() => handleAction(true)}
            className="bg-[#004b87] hover:bg-[#003870] text-white font-bold py-2.5 px-3 rounded-xl text-xs transition shadow-sm cursor-pointer"
          >
            ✓ Chấp Thuận Mở Cổng
          </button>
        </div>
      )}
    </div>
  );
};