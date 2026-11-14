import { API } from "./config.js";
import { state } from "./state.js";
import { $, storage } from "./utils.js";
import { api, run } from "./api.js";
import { boot } from "../boot.js";

// Đăng nhập / đăng xuất.

export function renderLogin() {
  $("#topbar").hidden = true;
  $("#app").innerHTML = `
    <div class="card login">
      <h1>Cổng thực tập</h1>
      <p class="muted">Hệ thống hỗ trợ thực tập bằng AI (VIN-15)</p>
      <form id="login-form">
        <div class="field"><label for="u">Tên đăng nhập</label><input id="u" autocomplete="username" required></div>
        <div class="field"><label for="p">Mật khẩu</label><input id="p" type="password" autocomplete="current-password" required></div>
        <button class="primary" type="submit">Đăng nhập</button>
      </form>
      <div id="sso"></div>
      <div class="demo-accounts muted"><p>Tài khoản demo (mật khẩu <code>demo123</code>):</p>
        <p>Sinh viên: <code>sv01</code> (chưa có hồ sơ), <code>sv03</code>, <code>sv04</code>, <code>sv05</code>, <code>sv06</code><br>
        Giảng viên: <code>gv01</code> (điều phối), <code>gv02</code>, <code>gv03</code><br>Quản trị viên (tùy chọn): <code>admin</code></p></div>
    </div>`;
  api("GET", "/auth/oidc/config").then((c) => {
    if (c.enabled) $("#sso").innerHTML = `<p style="margin-top:12px"><a class="badge info" href="${API}/auth/oidc/login">Đăng nhập bằng tài khoản trường (SSO)</a></p>`;
  }).catch(() => {});
  $("#login-form").onsubmit = async (ev) => {
    ev.preventDefault();
    const r = await run(() => api("POST", "/auth/login", { username: $("#u").value.trim().toLowerCase(), password: $("#p").value }));
    state.token = r.token;
    storage("set", "vin15_token", r.token);
    await boot();
  };
}

export function logout() {
  state.token = null; state.me = null; state.conversationId = null; state.chat = [];
  storage("del", "vin15_token");
  location.hash = "#/";
  renderLogin();
}
