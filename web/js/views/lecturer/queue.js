import { FIELDS } from "../../core/config.js";
import { $, esc, badge, fmtDate } from "../../core/utils.js";
import { api, openFile } from "../../core/api.js";
import { decisionBox, bindDecisions } from "../../components/decision.js";

// Hàng chờ phê duyệt của giảng viên.

export async function lecturerQueue() {
  const q = await api("GET", "/approvals/queue");
  const empty = !q.internships.length && !q.outlines.length && !q.extensions.length;
  $("#app").innerHTML = `<h1>Hàng chờ phê duyệt</h1>${empty ? `<div class="card muted">Không có mục nào chờ duyệt.</div>` : ""}
    ${q.internships.map((i) => `<div class="card"><div class="row spread"><h2>Hồ sơ đăng ký — ${esc(i.student.full_name)}</h2>${badge(i.status)}</div>
      <div class="grid2 small">${FIELDS.map(([n, l]) => `<div><span class="muted">${l}${(i.ai_fields || []).includes(n) ? ' <span class="badge" style="color:var(--ai)">AI điền</span>' : ""}</span><div>${esc(n.endsWith("date") ? fmtDate(i[n]) : n === "mode" ? (i[n] === "part_time" ? "Bán thời gian" : "Toàn thời gian") : i[n])}</div></div>`).join("")}</div>
      ${decisionBox("internship", i.id, i.version)}</div>`).join("")}
    ${q.outlines.map((o) => `<div class="card"><div class="row spread"><h2>Đề cương — ${esc(o.internship.student.full_name)}</h2><span class="small muted">phiên bản ${o.version}</span></div>
      <p class="pre">${esc(o.content)}</p>${aiOutline(o.ai_summary)}${decisionBox("outline", o.id, o.version)}</div>`).join("")}
    ${q.extensions.map((e) => `<div class="card"><h2>Gia hạn — ${esc(e.student.full_name)}: ${esc(e.milestone.name)}</h2>
      <p>${fmtDate(e.previous_due_date)} → <b>${fmtDate(e.requested_due_date)}</b></p><p class="pre">${esc(e.reason)}</p>
      ${e.evidence_id ? `<p class="small">Minh chứng kèm theo: <button class="link" data-file="${e.evidence_id}">mở file</button></p>` : ""}
      ${e.ai_summary ? `<div class="ai-box"><div class="ai-label">${esc(e.ai_summary.label)}</div><p>${esc(e.ai_summary.summary)}</p>
        ${e.ai_summary.related_clauses.map((c) => `<details><summary class="small">${esc(c.label)}</summary><p class="pre small">${esc(c.text)}</p></details>`).join("")}</div>` : ""}
      ${decisionBox("extension", e.id, null)}</div>`).join("")}`;
  document.querySelectorAll("[data-file]").forEach((b) => (b.onclick = () => openFile(b.dataset.file)));
  bindDecisions();
}

export function aiOutline(s) {
  if (!s) return `<p class="muted small">Không có gợi ý AI cho đề cương này.</p>`;
  return `<div class="ai-box"><div class="ai-label">${esc(s.label)}</div><p>${esc(s.summary)}</p>
    ${s.uncovered_outcomes.length ? `<p class="small"><b>Chuẩn đầu ra chưa thấy nhắc tới:</b></p><ul class="small">${s.uncovered_outcomes.map((c) => `<li>${esc(c.code)} — ${esc(c.text)}</li>`).join("")}</ul>` : `<p class="small">Đề cương có nhắc tới mọi chuẩn đầu ra học phần.</p>`}</div>`;
}
