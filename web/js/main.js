import { $ } from "./core/utils.js";
import { api } from "./core/api.js";
import { logout } from "./core/auth.js";
import { route } from "./router.js";
import { boot } from "./boot.js";

/* Cổng thực tập VIN-15 — SPA thuần JS (ES modules), gọi REST /api/v1. Router theo hash. */

$("#logout").onclick = logout;
$("#bell").onclick = async () => {
  const p = $("#notif-panel");
  p.hidden = !p.hidden;
  if (!p.hidden) { await api("POST", "/notifications/read-all"); $("#bell-count").hidden = true; }
};
window.addEventListener("hashchange", () => { $("#notif-panel").hidden = true; route(); });
boot();
