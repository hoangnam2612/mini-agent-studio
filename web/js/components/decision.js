import { $ } from "../core/utils.js";
import { api, run } from "../core/api.js";
import { route } from "../router.js";

// Hộp quyết định của giảng viên (duyệt / chỉnh sửa / từ chối).

export function decisionBox(kind, id, version) {
  const options = kind === "extension"
    ? [["approved", "Duyệt gia hạn", "primary"], ["rejected", "Từ chối", "danger"]]
    : [["approved", "Duyệt", "primary"], ["revision_requested", "Yêu cầu chỉnh sửa", ""], ["rejected", "Từ chối", "danger"]];
  return `<div class="field" style="margin-top:10px"><label>Lý do / nhận xét ${kind === "extension" ? "(bắt buộc)" : "(bắt buộc khi không duyệt)"}</label><textarea data-reason="${kind}-${id}" style="min-height:60px"></textarea></div>
    <div class="row">${options.map(([d, t, cls]) => `<button class="${cls}" data-decide="${kind}" data-id="${id}" data-version="${version ?? ""}" data-decision="${d}">${t}</button>`).join("")}</div>`;
}

export function bindDecisions() {
  const paths = { internship: (id) => `/internships/${id}/decision`, outline: (id) => `/outlines/${id}/decision`, extension: (id) => `/extensions/${id}/decision` };
  document.querySelectorAll("[data-decide]").forEach((b) => (b.onclick = async () => {
    const { decide, id, version, decision } = b.dataset;
    const body = { decision, reason: $(`[data-reason="${decide}-${id}"]`).value };
    if (version) body.version = Number(version);
    await run(() => api("POST", paths[decide](id), body), "Đã ghi nhận quyết định");
    route();
  }));
}
