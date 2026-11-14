import { API } from "./config.js";
import { state } from "./state.js";
import { toast } from "./utils.js";
import { logout } from "./auth.js";

// Gọi REST /api/v1, xử lý lỗi, SSE chat.

export async function api(method, path, body, isForm = false) {
  const headers = {};
  if (state.token) headers.Authorization = "Bearer " + state.token;
  if (body && !isForm) headers["Content-Type"] = "application/json";
  const res = await fetch(API + path, { method, headers, body: body ? (isForm ? body : JSON.stringify(body)) : undefined });
  if (res.status === 401 && state.token) { logout(); throw new Error("Phiên đăng nhập hết hạn"); }
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) {
    const err = new Error(errorText(data?.detail) || `Lỗi ${res.status}`);
    err.detail = data?.detail;
    err.status = res.status;
    throw err;
  }
  return data;
}

export function errorText(detail) {
  if (!detail) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join("; ");
  if (detail.message) return detail.message + (detail.citation ? ` (${detail.citation.doc} · ${detail.citation.path})` : "");
  return JSON.stringify(detail);
}

export async function run(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(okMsg); return r; }
  catch (e) { toast(e.message); throw e; }
}

export async function openFile(evidenceId) {
  const { url } = await run(() => api("GET", `/evidence/${evidenceId}/url`));
  window.open(url, "_blank", "noopener");
}
/* Đọc SSE từ POST /assistant/chat/stream (EventSource không hỗ trợ POST + header). */
export async function streamChat(message, onEvent) {
  const res = await fetch(API + "/assistant/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer " + state.token },
    body: JSON.stringify({ message, conversation_id: state.conversationId }),
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
