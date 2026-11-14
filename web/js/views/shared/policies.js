import { state } from "../../core/state.js";
import { $, esc, badge, fmtDate } from "../../core/utils.js";
import { api, run } from "../../core/api.js";
import { route } from "../../router.js";

// Văn bản quy định (dùng chung mọi vai trò).

export async function policiesView() {
  const docs = await api("GET", "/policies");
  $("#app").innerHTML = `<div class="card"><h1>Văn bản quy định</h1><div class="table-wrap"><table>
    <tr><th>Số hiệu</th><th>Tên văn bản</th><th>Hiệu lực</th><th>Trạng thái</th><th>Số đoạn</th></tr>
    ${docs.map((d) => `<tr><td><button class="link" data-doc="${d.id}">${esc(d.code)}</button></td><td>${esc(d.title)}<div class="small muted">${esc(d.issuer)}</div></td>
      <td>${fmtDate(d.effective_from)}${d.effective_to ? " – " + fmtDate(d.effective_to) : ""}</td><td>${badge(d.status)}</td><td>${d.chunk_count}</td></tr>`).join("")}
    </table></div><div id="doc-view"></div></div>
    ${state.me.can_manage_policies ? `<div class="card"><h2>Tải văn bản mới</h2><form id="pol-form">
      <div class="grid2"><div class="field"><label>Số hiệu</label><input name="code" required></div><div class="field"><label>Tên văn bản</label><input name="title" required></div>
      <div class="field"><label>Hiệu lực từ</label><input type="date" name="effective_from" required></div><div class="field"><label>Thay thế văn bản (số hiệu, nếu có)</label><input name="supersedes_code"></div>
      <div class="field"><label>Cơ quan ban hành</label><input name="issuer"></div><div class="field"><label>File (PDF/DOCX/MD/TXT, có dòng "Điều N.")</label><input type="file" name="file" accept=".pdf,.docx,.md,.txt" required></div></div>
      <button class="primary">Tải lên & lập chỉ mục</button></form></div>` : ""}`;
  document.querySelectorAll("[data-doc]").forEach((b) => (b.onclick = async () => {
    const d = await api("GET", `/policies/${b.dataset.doc}`);
    $("#doc-view").innerHTML = `<h2 style="margin-top:14px">${esc(d.code)} — ${esc(d.title)}</h2>${d.chunks.map((c) => `<details><summary>${esc(c.path)}</summary><p class="pre">${esc(c.text)}</p></details>`).join("")}`;
  }));
  if ($("#pol-form")) $("#pol-form").onsubmit = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    if (!fd.get("supersedes_code")) fd.delete("supersedes_code");
    await run(() => api("POST", "/policies", fd, true), "Đã tải và lập chỉ mục văn bản");
    route();
  };
}
