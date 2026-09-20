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

  if (!review) {
    return (
      <div className="bg-white border border-slate-300 rounded-xl p-5 shadow-sm text-center">
        <div className="text-2xl mb-1">✅</div>
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
        ? "✓ Đã chấp thuận mở barie ra cho xe " + review.plate_number + "!"
        : "✕ Đã từ chối cho ra. Barie giữ nguyên đóng."
    );
  };

  return (
    <div className="bg-white border-2 border-amber-400 rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between pb-2 mb-3 border-b border-amber-200">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-ping"></span>
          <h2 className="font-extrabold text-sm text-[#004b87] uppercase">
            Yêu Cầu Xác Nhận Thủ Công
          </h2>
        </div>
        <span className="text-[10px] font-mono bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 rounded font-bold">
          {review.request_id}
        </span>
      </div>

      <p className="text-xs text-slate-600 mb-3 leading-relaxed">
        Hệ thống phát hiện độ tương đồng khuôn mặt lúc ra nằm trong vùng bất định (0.45 - 0.65). Cần cán bộ quản trị kiểm tra.
      </p>

      <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 mb-4 space-y-2.5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500">Biển số nhận diện:</span>
          <span className="font-mono font-bold text-slate-900 bg-white px-2 py-0.5 rounded border border-slate-300">
            {review.plate_number}
          </span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500">Mã lý do:</span>
          <span className="text-amber-700 font-bold">{review.reason_code}</span>
        </div>

        {/* Cosine similarity meter */}
        <div className="space-y-1 pt-1">
          <div className="flex justify-between text-[11px] font-medium">
            <span className="text-slate-600">Độ tương đồng Cosine:</span>
            <span className="font-mono font-bold text-amber-700">
              {review.similarity_score.toFixed(2)} / 1.00
            </span>
          </div>
          <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden flex border border-slate-300">
            <div className="bg-red-400 h-full" style={{ width: "45%" }} title="Từ chối (< 0.45)"></div>
            <div className="bg-amber-400 h-full" style={{ width: "20%" }} title="Cần duyệt (0.45 - 0.65)"></div>
            <div className="bg-emerald-500 h-full" style={{ width: "35%" }} title="Khớp (> 0.65)"></div>
          </div>
          <div className="flex justify-between text-[10px] text-slate-500">
            <span>0.0 (Từ chối)</span>
            <span className="text-amber-700 font-bold">0.45 - 0.65</span>
            <span>1.0 (Khớp)</span>
          </div>
        </div>
      </div>

      {resolvedMessage ? (
        <div className="text-center py-2.5 bg-emerald-50 border border-emerald-300 rounded text-xs text-emerald-800 font-bold">
          {resolvedMessage}
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => handleAction(false)}
            className="bg-red-50 hover:bg-red-100 text-red-700 border border-red-300 font-bold py-2 px-3 rounded text-xs transition cursor-pointer"
          >
            ✕ Từ Chối
          </button>
          <button
            onClick={() => handleAction(true)}
            className="bg-[#004b87] hover:bg-[#003870] text-white font-bold py-2 px-3 rounded text-xs transition shadow-sm cursor-pointer"
          >
            ✓ Chấp Thuận Mở Cổng
          </button>
        </div>
      )}
    </div>
  );
};