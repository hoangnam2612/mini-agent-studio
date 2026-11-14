import { state } from "../../core/state.js";
import { $, esc } from "../../core/utils.js";
import { streamChat } from "../../core/api.js";

// Trợ lý AI hỏi đáp quy định (dùng chung mọi vai trò).

export function assistantView() {
  $("#app").innerHTML = `<div class="card"><h1>Trợ lý chính sách thực tập</h1>
    <p class="muted small">Trợ lý chỉ trả lời theo văn bản quy định đang có hiệu lực và luôn dẫn nguồn. Trợ lý không duyệt hay cam kết kết quả — mọi quyết định do giảng viên đưa ra.</p>
    <div class="chat" id="chat"></div>
    <form class="row" id="ask" style="margin-top:10px"><input id="q" placeholder="Ví dụ: Thời gian thực tập tối thiểu là bao lâu?" maxlength="2000" style="flex:1"><button class="primary">Hỏi</button></form>
    <div class="row small" style="margin-top:8px">${["Thời gian thực tập tối thiểu là bao nhiêu tuần?", "Khi nào phải nộp đề cương?", "Em có được gia hạn nộp báo cáo không?", "Mỗi tuần cần bao nhiêu giờ?"].map((s) => `<button class="link" data-suggest="${esc(s)}">${esc(s)}</button>`).join("")}</div></div>`;
  drawChat();
  document.querySelectorAll("[data-suggest]").forEach((b) => (b.onclick = () => { $("#q").value = b.dataset.suggest; $("#ask").requestSubmit(); }));
  $("#ask").onsubmit = async (ev) => {
    ev.preventDefault();
    const q = $("#q").value.trim();
    if (!q) return;
    $("#q").value = "";
    state.chat.push({ role: "user", content: q });
    const msg = { role: "assistant", content: "", status: "Đang gửi câu hỏi…" };
    state.chat.push(msg);
    drawChat();
    try {
      await streamChat(q, (ev) => {
        if (ev.type === "stage") msg.status = ev.label + "…";
        else if (ev.type === "delta") { msg.status = ""; msg.content += ev.text; }
        else if (ev.type === "done") {
          state.conversationId = ev.conversation_id;
          Object.assign(msg, { content: ev.answer, citations: ev.citations, suggest: ev.suggest_extension, mode: ev.mode, status: "" });
        } else if (ev.type === "error") throw new Error(ev.detail);
        drawChat();
      });
    } catch (e) {
      Object.assign(msg, { content: e.message, status: "" });
    }
    drawChat();
  };
}
export function drawChat() {
  const el = $("#chat");
  if (!el) return;
  el.innerHTML = state.chat.map((m) => `<div class="msg ${m.role}">${m.status ? `<span class="muted small">${esc(m.status)}</span>` : ""}${esc(m.content)}
    ${m.mode?.startsWith("extractive") ? `<div class="small muted" style="margin-top:6px">Trích nguyên văn quy định (không diễn giải).</div>` : ""}
    ${m.citations?.length ? `<div class="cites"><b>Nguồn:</b>${m.citations.map((c) => `<details><summary>[${c.n}] ${esc(c.label)}</summary><div class="pre">${esc(c.excerpt)}</div></details>`).join("")}</div>` : ""}
    ${m.suggest ? `<div style="margin-top:8px"><a href="#/">→ Mở mục Mốc để tạo yêu cầu gia hạn</a></div>` : ""}</div>`).join("") || `<p class="muted">Hãy đặt câu hỏi về thủ tục, thời hạn hay quy định thực tập.</p>`;
  el.scrollTop = el.scrollHeight;
}
