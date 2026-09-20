export class ReviewService {
  /**
   * Tạo yêu cầu xác nhận thủ công gửi lên Firebase.
   * Dashboard KHÔNG gửi lệnh mở barie trực tiếp.
   */
  async submitReviewDecision(requestId: string, decision: "APPROVED" | "REJECTED") {
    // Ghi trạng thái duyệt lên Firebase
  }
}