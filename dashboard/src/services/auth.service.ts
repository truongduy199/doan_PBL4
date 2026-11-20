import { ApiClient } from "./api.client";
import { UserProfile } from "../shared/types";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
  server_time: string;
}

export class AuthService {
  static async login(username: string, password: string): Promise<LoginResponse> {
    const res = await ApiClient.post<LoginResponse>("/api/auth/login", {
      username,
      password,
    });
    ApiClient.setToken(res.access_token);
    return res;
  }

  static async logout(): Promise<void> {
    try {
      await ApiClient.post("/api/auth/logout");
    } finally {
      ApiClient.setToken(null);
    }
  }

  static async getCurrentUser(): Promise<UserProfile> {
    return ApiClient.get<UserProfile>("/api/me");
  }
}
