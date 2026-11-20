import React, { useState } from "react";
import { AuthService } from "../../services/auth.service";
import { ApiError } from "../../services/api.client";
import { UserProfile } from "../../shared/types";

interface LoginPageProps {
  onLoginSuccess: (user: UserProfile) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState<string>("viet_user");
  const [password, setPassword] = useState<string>("Viet@123");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) return;
    setErrorMessage(null);
    setIsLoading(true);
    try {
      const res = await AuthService.login(username.trim(), password);
      onLoginSuccess(res.user);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(`[${err.reasonCode}] ${err.message}`);
      } else {
        setErrorMessage("Đã xảy ra lỗi khi đăng nhập. Vui lòng thử lại.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const fillDemoUser = () => {
    setUsername("viet_user");
    setPassword("Viet@123");
    setErrorMessage(null);
  };

  const fillDemoAdmin = () => {
    setUsername("admin");
    setPassword("Admin@123");
    setErrorMessage(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-[#002f57] to-slate-900 flex flex-col justify-center items-center px-4 py-8 text-slate-800">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
        {/* Institutional Header Banner */}
        <div className="bg-[#004b87] px-6 py-5 text-white border-b border-blue-900">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-amber-400 text-slate-950 font-black text-base flex flex-col items-center justify-center shadow">
              <span>PBL4</span>
              <span className="text-[9px] font-bold">DUT • IoT</span>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-amber-300 font-bold">
                ĐH Bách Khoa - ĐH Đà Nẵng • Khoa CNTT
              </div>
              <h1 className="text-lg font-extrabold tracking-tight">
                Hệ Thống Bãi Đỗ Xe Thông Minh
              </h1>
              <p className="text-xs text-blue-100">
                MySQL/InnoDB • Đặt chỗ 60 phút • Nhận diện Biển số &amp; Khuôn mặt 1:1
              </p>
            </div>
          </div>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-xs text-slate-700 space-y-1.5">
            <div className="font-bold text-[#004b87] flex items-center justify-between">
              <span>Tài khoản định danh nội bộ (Demo Ready):</span>
            </div>
            <p className="text-[11px] text-slate-600">
              Hệ thống sử dụng tài khoản, xe và mẫu khuôn mặt đã chuẩn bị sẵn trong MySQL (không mở đăng ký tự do trên web). Hỗ trợ mở song song <strong>USER</strong> và <strong>ADMIN</strong> trên 2 trình duyệt/tab khác nhau.
            </p>
            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={fillDemoUser}
                className="flex-1 bg-white hover:bg-blue-100 text-[#004b87] border border-blue-300 font-bold py-1.5 px-2.5 rounded-lg text-xs transition cursor-pointer"
              >
                👤 Điền USER (viet_user)
              </button>
              <button
                type="button"
                onClick={fillDemoAdmin}
                className="flex-1 bg-white hover:bg-amber-50 text-amber-900 border border-amber-300 font-bold py-1.5 px-2.5 rounded-lg text-xs transition cursor-pointer"
              >
                🛡️ Điền ADMIN (admin)
              </button>
            </div>
          </div>

          {errorMessage && (
            <div
              role="alert"
              className="bg-red-50 border-2 border-red-400 text-red-800 px-3.5 py-2.5 rounded-xl text-xs font-semibold"
            >
              ⚠️ {errorMessage}
            </div>
          )}

          <div>
            <label
              htmlFor="username"
              className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1"
            >
              Tên đăng nhập
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#004b87]"
              placeholder="Nhập username (ví dụ: viet_user)"
            />
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-xs font-bold uppercase tracking-wider text-slate-600 mb-1"
            >
              Mật khẩu
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#004b87]"
              placeholder="Nhập mật khẩu"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-[#004b87] hover:bg-[#003968] disabled:bg-slate-400 text-white font-extrabold py-3 rounded-xl text-sm shadow-md transition cursor-pointer"
          >
            {isLoading ? "⏳ Đang xác thực với MySQL..." : "Đăng Nhập Hệ Thống →"}
          </button>
        </form>
      </div>
    </div>
  );
};
