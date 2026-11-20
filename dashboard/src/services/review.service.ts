import { ApiClient } from "./api.client";
import { ManualReviewItem } from "../shared/types";

export interface AdminReviewsResponse {
  reviews: ManualReviewItem[];
  count: number;
  server_time: string;
  server_time_vn: string;
}

export class ReviewService {
  static async listAdminReviews(includeResolved = false): Promise<AdminReviewsResponse> {
    return ApiClient.get<AdminReviewsResponse>(
      `/api/admin/reviews?include_resolved=${includeResolved ? "true" : "false"}`
    );
  }

  static async submitDecision(
    eventId: string,
    action: "APPROVE" | "DENY",
    reason: string
  ): Promise<Record<string, unknown>> {
    return ApiClient.post<Record<string, unknown>>(
      `/api/admin/reviews/${encodeURIComponent(eventId)}/decision`,
      { action, reason }
    );
  }
}
