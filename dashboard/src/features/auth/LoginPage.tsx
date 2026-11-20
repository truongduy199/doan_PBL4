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
  const [showPassword, setShowPassword] = useState<boolean>(false);
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
        setErrorMessage("Không thể kết nối tới máy chủ đăng nhập. Vui lòng thử lại.");
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
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-[#002f57] to-slate-900 flex flex-col justify-center items-center px-4 py-8 text-slate-800">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden">
        {/* Institutional Header Banner */}
        <div className="bg-gradient-to-r from-[#003366] to-[#004b87] px-6 py-5 text-white border-b border-blue-900">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-amber-400 text-slate-950 font-black text-base flex flex-col items-center justify-center shadow-md flex-shrink-0">
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
              <p className="text-xs text-blue-100 mt-0.5">
                MySQL/InnoDB • Đặt chỗ 60 phút • Nhận diện Biển số &amp; Khuôn mặt 1:1
              </p>
            </div>
          </div>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-3.5 text-xs text-slate-700 space-y-2">
            <div className="font-extrabold text-[#004b87]">
              Tài khoản định danh nội bộ (Demo Ready)
            </div>
            <p className="text-[11px] text-slate-600 leading-relaxed">
              Tài khoản, xe định danh và mẫu khuôn mặt 512-D được quản lý nội bộ trong MySQL (không mở đăng ký công khai trên web). Hỗ trợ chạy song song <strong>USER</strong> và <strong>ADMIN</strong> trên 2 tab/trình duyệt khác nhau.
            </p>
            <div className="flex items-center gap-2 pt-0.5">
              <button
                type="button"
                onClick={fillDemoUser}
                className="flex-1 bg-white hover:bg-blue-100 text-[#004b87] border border-blue-300 font-bold py-2 px-2.5 rounded-xl text-xs transition cursor-pointer shadow-2xs"
              >
                👤 USER (viet_user)
              </button>
              <button
                type="button"
                onClick={fillDemoAdmin}
                className="flex-1 bg-white hover:bg-amber-50 text-amber-900 border border-amber-300 font-bold py-2 px-2.5 rounded-xl text-xs transition cursor-pointer shadow-2xs"
              >
                🛡️ ADMIN (admin)
              </button>
            </div>
          </div>

          {errorMessage && (
            <div
              role="alert"
              className="bg-rose-50 border-2 border-rose-400 text-rose-900 px-3.5 py-2.5 rounded-xl text-xs font-semibold"
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
            <div className="relative">
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full px-3.5 py-2.5 pr-12 rounded-xl border border-slate-300 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#004b87]"
                placeholder="Nhập mật khẩu"
              />
              <button
                type="button"
                onClick={() => setShowPassword((prev) => !prev)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-500 hover:text-slate-800 px-2 py-1 cursor-pointer"
                aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
              >
                {showPassword ? "Ẩn" : "Hiện"}
              </button>
            </div>
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
