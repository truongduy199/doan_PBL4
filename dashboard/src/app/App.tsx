import React, { useEffect, useState } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useNavigate,
} from "react-router-dom";
import { AdminDashboardPage } from "../features/admin/AdminDashboardPage";
import { LoginPage } from "../features/auth/LoginPage";
import { UserBookingPortal } from "../features/user-portal/UserBookingPortal";
import { ApiClient } from "../services/api.client";
import { AuthService } from "../services/auth.service";
import { UserProfile } from "../shared/types";

const AppRoutes: React.FC = () => {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [isCheckingSession, setIsCheckingSession] = useState<boolean>(true);
  const navigate = useNavigate();

  useEffect(() => {
    let mounted = true;
    const checkSession = async () => {
      const token = ApiClient.getToken();
      if (!token) {
        if (mounted) setIsCheckingSession(false);
        return;
      }
      try {
        const profile = await AuthService.getCurrentUser();
        if (mounted) {
          setCurrentUser(profile);
        }
      } catch {
        ApiClient.setToken(null);
        if (mounted) {
          setCurrentUser(null);
        }
      } finally {
        if (mounted) {
          setIsCheckingSession(false);
        }
      }
    };
    checkSession();
    return () => {
      mounted = false;
    };
  }, []);

  const handleLoginSuccess = (user: UserProfile) => {
    setCurrentUser(user);
    if (user.role === "admin") {
      navigate("/admin", { replace: true });
    } else {
      navigate("/user", { replace: true });
    }
  };

  const handleLogout = async () => {
    await AuthService.logout();
    setCurrentUser(null);
    navigate("/login", { replace: true });
  };

  if (isCheckingSession) {
    return (
      <div className="min-h-screen bg-slate-900 text-white flex items-center justify-center text-sm font-bold">
        ⏳ Đang kiểm tra phiên đăng nhập...
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={
          currentUser ? (
            <Navigate
              to={currentUser.role === "admin" ? "/admin" : "/user"}
              replace
            />
          ) : (
            <LoginPage onLoginSuccess={handleLoginSuccess} />
          )
        }
      />

      <Route
        path="/user"
        element={
          !currentUser ? (
            <Navigate to="/login" replace />
          ) : currentUser.role === "admin" ? (
            <Navigate to="/admin" replace />
          ) : (
            <UserBookingPortal user={currentUser} onLogout={handleLogout} />
          )
        }
      />

      <Route
        path="/admin"
        element={
          !currentUser ? (
            <Navigate to="/login" replace />
          ) : currentUser.role !== "admin" ? (
            <Navigate to="/user" replace />
          ) : (
            <AdminDashboardPage user={currentUser} onLogout={handleLogout} />
          )
        }
      />

      <Route
        path="*"
        element={
          <Navigate
            to={
              !currentUser
                ? "/login"
                : currentUser.role === "admin"
                ? "/admin"
                : "/user"
            }
            replace
          />
        }
      />
    </Routes>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
};
