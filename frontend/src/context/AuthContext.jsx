import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "../lib/api";

// Phiên đăng nhập: token, hồ sơ người dùng (/me) và cấu hình đợt (/config).

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [me, setMe] = useState(null);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(Boolean(getToken()));

  const logout = useCallback(() => {
    setToken(null);
    setMe(null);
    setConfig(null);
    setLoading(false);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, c] = await Promise.all([api("GET", "/me"), api("GET", "/config")]);
      setMe(m);
      setConfig(c);
    } catch (_) {
      logout();
    } finally {
      setLoading(false);
    }
  }, [logout]);

  useEffect(() => { setUnauthorizedHandler(logout); }, [logout]);
  useEffect(() => { if (getToken()) load(); }, [load]);

  const login = useCallback(async (username, password) => {
    const r = await api("POST", "/auth/login", { username: username.trim().toLowerCase(), password });
    setToken(r.token);
    await load();
  }, [load]);

  /** Dùng cho callback SSO: nhận token từ URL. */
  const loginWithToken = useCallback(async (t) => {
    setToken(t);
    await load();
  }, [load]);

  const value = useMemo(
    () => ({ me, config, loading, login, loginWithToken, logout }),
    [me, config, loading, login, loginWithToken, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
