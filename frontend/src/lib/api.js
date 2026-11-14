import { API, TOKEN_KEY } from "./config";
import { storage } from "./format";

// Gọi REST /api/v1, xử lý lỗi, SSE chat. Token giữ ở module này (AuthContext đồng bộ).

let token = storage("get", TOKEN_KEY);
let onUnauthorized = () => {};

export const getToken = () => token;
export function setToken(t) {
  token = t;
  if (t) storage("set", TOKEN_KEY, t);
  else storage("del", TOKEN_KEY);
}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

export function errorText(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join("; ");
  if (detail.message) return detail.message + (detail.citation ? ` (${detail.citation.doc} · ${detail.citation.path})` : "");
  return JSON.stringify(detail);
}

export async function api(method, path, body, isForm = false) {
  const headers = {};
  if (token) headers.Authorization = "Bearer " + token;
  if (body && !isForm) headers["Content-Type"] = "application/json";
  const res = await fetch(API + path, { method, headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined });
  if (res.status === 401 && token) { onUnauthorized(); throw new Error("Phiên đăng nhập hết hạn"); }
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) {
    const err = new Error(errorText(data?.detail) || `Lỗi ${res.status}`);
    err.detail = data?.detail;
    err.status = res.status;
    throw err;
  }
  return data;
}

/** FormData từ object (bỏ giá trị rỗng). */
export function formData(obj) {
  const fd = new FormData();
  Object.entries(obj).forEach(([k, v]) => { if (v != null && v !== "") fd.append(k, v); });
  return fd;
}

/* Đọc SSE từ POST /assistant/chat/stream (EventSource không hỗ trợ POST + header). */
export async function streamChat(message, conversationId, onEvent) {
  const res = await fetch(API + "/assistant/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(errorText(data?.detail) || `Lỗi ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)));
    }
  }
}

/** Tải file xuất (cần Bearer token nên không dùng link thường). */
export async function downloadFile(path, fallbackName) {
  const res = await fetch(API + path, { headers: { Authorization: "Bearer " + token } });
  if (!res.ok) throw new Error(`Không xuất được file (${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = (res.headers.get("content-disposition") || "").split('filename="')[1]?.replace('"', "") || fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
