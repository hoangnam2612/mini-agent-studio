import { state } from "./core/state.js";
import { toast, storage } from "./core/utils.js";
import { api } from "./core/api.js";
import { renderLogin, logout } from "./core/auth.js";
import { route } from "./router.js";

// Khởi động: nhận token (kể cả callback SSO), tải /me + /config, vào router.

export async function boot() {
  // Callback SSO trả token trong fragment: #/sso/<token> hoặc #/sso-error/<lý do>
  if (location.hash.startsWith("#/sso/")) {
    state.token = location.hash.slice("#/sso/".length);
    storage("set", "vin15_token", state.token);
    history.replaceState(null, "", "#/");
  } else if (location.hash.startsWith("#/sso-error/")) {
    const reason = decodeURIComponent(location.hash.slice("#/sso-error/".length));
    history.replaceState(null, "", "#/");
    setTimeout(() => toast("Đăng nhập SSO thất bại: " + reason), 0);
  }
  state.token = state.token || storage("get", "vin15_token");
  if (!state.token) return renderLogin();
  try {
    [state.me, state.config] = await Promise.all([api("GET", "/me"), api("GET", "/config")]);
  } catch (_) {
    return logout();
  }
  route();
}
