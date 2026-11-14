import { API, STATUS, SEVERITY } from "../../core/config.js";
import { state } from "../../core/state.js";
import { $, esc, badge, fmtDate, toast } from "../../core/utils.js";
import { api } from "../../core/api.js";

// Danh sách sinh viên: lọc, sắp xếp, phân trang, xuất file.

const summaryFilters = { q: "", status: "", program: "", risk: "", lecturer_id: "", sort: "risk", order: "desc", page: 1 };

export function summaryQuery(extra = {}) {
  const p = new URLSearchParams();
  Object.entries({ ...summaryFilters, ...extra }).forEach(([k, v]) => { if (v !== "" && v != null) p.set(k, v); });
  return p.toString();
}

export async function lecturerStudents() {
  const isAdmin = state.me.role === "admin";
  const [data, users] = await Promise.all([
    api("GET", `/internships-summary?${summaryQuery({ page_size: 25 })}`),
    isAdmin ? api("GET", "/admin/users") : Promise.resolve([]),
  ]);
  const f = summaryFilters;
  const opt = (value, label, current) => `<option value="${esc(value)}" ${String(current) === String(value) ? "selected" : ""}>${esc(label)}</option>`;
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  const sortHead = (key, label) => `<th><button class="link" data-sort="${key}">${label}${f.sort === key ? (f.order === "asc" ? " ▲" : " ▼") : ""}</button></th>`;
  $("#app").innerHTML = `<div class="card"><div class="row spread"><h1>${isAdmin ? "Danh sách thực tập toàn khóa" : "Sinh viên phụ trách"}</h1>
      <div class="row"><button data-export="csv">Xuất CSV</button><button data-export="xlsx">Xuất Excel</button></div></div>
    <div class="grid2">
      <div class="field"><label>Tìm (tên, mã SV, doanh nghiệp)</label><input id="sf-q" value="${esc(f.q)}"></div>
      <div class="field"><label>Trạng thái</label><select id="sf-status">${opt("", "Tất cả", f.status)}${Object.keys(STATUS).filter((s) => ["draft", "submitted", "revision_requested", "approved", "rejected", "in_progress", "completed"].includes(s)).map((s) => opt(s, STATUS[s][0], f.status)).join("")}</select></div>
      <div class="field"><label>Ngành</label><select id="sf-program">${opt("", "Tất cả", f.program)}${["Công nghệ thông tin", "Quản trị kinh doanh"].concat(data.facets.programs).filter((v, i, a) => a.indexOf(v) === i).map((p) => opt(p, p, f.program)).join("")}</select></div>
      <div class="field"><label>Mức rủi ro</label><select id="sf-risk">${[["", "Tất cả"], ["any", "Có cảnh báo"], ["none", "Không cảnh báo"], ["critical", "Nghiêm trọng"], ["warning", "Cảnh báo"], ["info", "Thông tin"]].map(([v, l]) => opt(v, l, f.risk)).join("")}</select></div>
      ${isAdmin ? `<div class="field"><label>Giảng viên</label><select id="sf-lecturer">${opt("", "Tất cả", f.lecturer_id)}${users.filter((u) => u.role === "lecturer").map((u) => opt(u.id, u.full_name, f.lecturer_id)).join("")}</select></div>` : ""}
    </div>
    <p class="small muted">${data.total} hồ sơ · trang ${data.page}/${pages}</p>
    <div class="table-wrap"><table>
      <tr>${sortHead("student", "Sinh viên")}${sortHead("company", "Doanh nghiệp")}${sortHead("status", "Trạng thái")}${sortHead("progress", "% mốc")}${sortHead("next_due", "Mốc kế tiếp")}${sortHead("risk", "Cảnh báo")}${isAdmin ? "<th>GV</th>" : ""}</tr>
      ${data.items.map((r) => `<tr><td><a href="#/internship/${r.id}">${esc(r.student_name)}</a><div class="small muted">${esc(r.student_code)} · ${esc(r.program)}</div></td>
        <td>${esc(r.company || "—")}</td><td>${badge(r.status)}</td><td>${r.progress_pct}%</td>
        <td class="small">${r.next_milestone ? `${esc(r.next_milestone)}<div class="muted">${fmtDate(r.next_due)} ${r.next_status === "overdue" ? badge("overdue") : ""}</div>` : "—"}</td>
        <td>${r.open_flags ? `${badge(r.max_severity, SEVERITY)} ×${r.open_flags}` : '<span class="muted">—</span>'}</td>${isAdmin ? `<td class="small">${esc(r.lecturer)}</td>` : ""}</tr>`).join("") || `<tr><td colspan="7" class="muted">Không có hồ sơ phù hợp.</td></tr>`}
    </table></div>
    <div class="row" style="margin-top:8px"><button id="sf-prev" ${data.page <= 1 ? "disabled" : ""}>← Trước</button><button id="sf-next" ${data.page >= pages ? "disabled" : ""}>Sau →</button></div></div>`;
  const apply = (changes) => { Object.assign(summaryFilters, changes); lecturerStudents(); };
  $("#sf-q").onchange = (e) => apply({ q: e.target.value.trim(), page: 1 });
  $("#sf-status").onchange = (e) => apply({ status: e.target.value, page: 1 });
  $("#sf-program").onchange = (e) => apply({ program: e.target.value, page: 1 });
  $("#sf-risk").onchange = (e) => apply({ risk: e.target.value, page: 1 });
  if ($("#sf-lecturer")) $("#sf-lecturer").onchange = (e) => apply({ lecturer_id: e.target.value, page: 1 });
  $("#sf-prev").onclick = () => apply({ page: f.page - 1 });
  $("#sf-next").onclick = () => apply({ page: f.page + 1 });
  document.querySelectorAll("[data-sort]").forEach((b) => (b.onclick = () => {
    const key = b.dataset.sort;
    apply({ sort: key, order: f.sort === key && f.order === "desc" ? "asc" : "desc", page: 1 });
  }));
  document.querySelectorAll("[data-export]").forEach((b) => (b.onclick = () => downloadExport(b.dataset.export)));
}

/* Tải file xuất có kèm Bearer token (link thường không gửi được header). */
export async function downloadExport(format) {
  const query = summaryQuery({ format, page: undefined });
  const res = await fetch(`${API}/internships-summary/export?${query}`, { headers: { Authorization: "Bearer " + state.token } });
  if (!res.ok) return toast(`Không xuất được file (${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = (res.headers.get("content-disposition") || "").split('filename="')[1]?.replace('"', "") || `danh-sach.${format}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
