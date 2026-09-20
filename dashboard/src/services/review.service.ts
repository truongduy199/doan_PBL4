import { ref, onValue, set } from "firebase/database";
import { db } from "./firebase";
import { ReviewRequest } from "../shared/types";

export const defaultReview: ReviewRequest = {
  request_id: "REQ-0920-01",
  session_id: "SES-20260920-001",
  plate_number: "43A-123.45",
  reason_code: "ERR_FACE_UNCERTAIN",
  similarity_score: 0.58,
  status: "PENDING",
  created_at: "14:41:50",
};

export class ReviewService {
  /**
   * Lắng nghe danh sách yêu cầu duyệt ngoại lệ từ Firebase.
   */
  static subscribeReviews(callback: (review: ReviewRequest | null) => void): () => void {
    if (!db) {
      callback(defaultReview);
      return () => {};
    }

    try {
      const reviewRef = ref(db, "review_requests");
      const unsubscribe = onValue(reviewRef, (snapshot) => {
        const data = snapshot.val();
        if (data && typeof data === "object") {
          const list: ReviewRequest[] = Object.values(data);
          // Tìm yêu cầu pending gần nhất
          const pending = list.find((r) => r && r.status === "PENDING");
          callback(pending || null);
        } else {
          callback(null);
        }
      });
      return unsubscribe;
    } catch (e) {
      console.warn("Could not subscribe to review_requests:", e);
      callback(defaultReview);
      return () => {};
    }
  }

  /**
   * Gửi quyết định duyệt (APPROVED hoặc REJECTED) lên Firebase.
   */
  static async submitDecision(requestId: string, decision: "APPROVED" | "REJECTED"): Promise<void> {
    if (!db) return;
    try {
      const statusRef = ref(db, `review_requests/${requestId}/status`);
      await set(statusRef, decision);
    } catch (e) {
      console.warn("Could not write review decision to Firebase:", e);
    }
  }
}