import React from "react";
import { EmptyState } from "../../shared/components/ui";

// Retained for a future evaluation route. Never present sample values as measured results.
export const ReportsView: React.FC = () => <section className="panel">
  <div className="panel-header"><div><h2>Đánh giá hệ thống</h2><p>Kết quả đo từ dữ liệu kiểm thử độc lập.</p></div></div>
  <EmptyState>Chưa có báo cáo đánh giá được nạp. Độ chính xác và độ trễ sẽ được hiển thị khi có số liệu đã kiểm chứng.</EmptyState>
</section>;
