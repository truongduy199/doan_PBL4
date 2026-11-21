import React, { useState } from "react";
import { AuthService } from "../../services/auth.service";
import { ApiError } from "../../services/api.client";
import { UserProfile } from "../../shared/types";
import { Notice, ParkingBrand } from "../../shared/components/ui";

interface LoginPageProps { onLoginSuccess: (user: UserProfile) => void; sessionNotice?: string | null; }

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess, sessionNotice }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (isLoading) return;
    setErrorMessage(null);
    setIsLoading(true);
    try {
      const response = await AuthService.login(username.trim(), password);
      onLoginSuccess(response.user);
    } catch (error) {
      setErrorMessage(error instanceof ApiError ? error.message : "Không thể kết nối máy chủ. Vui lòng thử lại.");
    } finally { setIsLoading(false); }
  };

  const fillDemoAccount = (role: "user" | "admin") => {
    setUsername(role === "admin" ? "admin" : "viet_user");
    setPassword(role === "admin" ? "Admin@123" : "Viet@123");
    setErrorMessage(null);
  };

  return <div className="login-page"><ParkingBrand />
    <section className="login-card" aria-labelledby="login-title">
      <h1 id="login-title">Đăng nhập</h1>
      <p>Xem chỗ đỗ, giữ chỗ và quản lý lượt gửi xe.</p>
      {errorMessage && <Notice tone="error">{errorMessage}</Notice>}
      {sessionNotice && <Notice tone="warning">{sessionNotice}</Notice>}
      <form onSubmit={handleSubmit}>
        <div className="field"><label htmlFor="username">Tên đăng nhập</label>
          <input className="input" id="username" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" placeholder="Nhập tên đăng nhập" required autoFocus />
        </div>
        <div className="field"><label htmlFor="password">Mật khẩu</label><div className="password-field">
          <input className="input" id="password" type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" placeholder="Nhập mật khẩu" required />
          <button className="password-toggle" type="button" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}>{showPassword ? "Ẩn" : "Hiện"}</button>
        </div></div>
        <button className="button button-primary button-full" disabled={isLoading} type="submit">{isLoading ? "Đang đăng nhập…" : "Đăng nhập"}</button>
      </form>
      <p className="login-help">Sử dụng tài khoản được cấp. Liên hệ người quản lý bãi nếu bạn chưa có tài khoản.</p>
      <details className="demo-accounts"><summary>Tài khoản thử nghiệm</summary><div className="row">
        <button type="button" className="button button-small" onClick={() => fillDemoAccount("user")}>Người gửi xe</button>
        <button type="button" className="button button-small" onClick={() => fillDemoAccount("admin")}>Quản trị viên</button>
      </div></details>
    </section>
    <p className="login-footer">PBL4 · Đại học Bách khoa Đà Nẵng</p>
  </div>;
};
