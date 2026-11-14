// UI smoke: chạy web/app.js thật trong jsdom, gọi API thật ở localhost:8000.
import { JSDOM } from "jsdom";

const BASE = "http://localhost:8000";
const html = await (await fetch(BASE + "/")).text();
const appJs = await (await fetch(BASE + "/app.js")).text();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function token(u) {
  const r = await fetch(BASE + "/api/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: u, password: "demo123" }) });
  return (await r.json()).token;
}

async function open(user) {
  const dom = new JSDOM(html, { url: BASE + "/", runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window;
  w.fetch = (url, opts) => fetch(new URL(url, BASE), opts);
  w.TextDecoder = TextDecoder; // jsdom không có — app.js cần để đọc SSE
  w.open = () => null;
  w.prompt = () => null;
  w.HTMLFormElement.prototype.requestSubmit = function () { this.dispatchEvent(new w.Event("submit", { cancelable: true })); };
  if (user) w.localStorage.setItem("vin15_token", await token(user));
  const errors = [];
  w.addEventListener("error", (e) => errors.push(e.message));
  w.addEventListener("unhandledrejection", (e) => errors.push(String(e.reason?.message || e.reason)));
  w.eval(appJs);
  await sleep(600);
  return { w, errors, text: () => w.document.querySelector("#app").textContent.replace(/\s+/g, " ") };
}

async function go(page, hash) { page.w.location.hash = hash; await sleep(600); }

const results = [];
function check(name, cond, extra = "") { results.push(`${cond ? "PASS" : "FAIL"} ${name}${cond ? "" : " :: " + extra}`); }

// Đăng nhập
let p = await open(null);
check("login screen", p.text().includes("Đăng nhập") && p.text().includes("sv01"), p.text().slice(0, 200));

// Sinh viên chưa có hồ sơ → tạo → form
p = await open("sv01");
check("sv01 empty state", p.text().includes("Tạo hồ sơ đăng ký"), p.text().slice(0, 200));
p.w.document.querySelector("#create").click();
await sleep(800);
check("sv01 form after create", p.text().includes("Thông tin đăng ký") && p.w.document.querySelector("#f-company_name"), p.text().slice(0, 200));
p.w.document.querySelector("#check").click();
await sleep(800);
check("sv01 validation shows citation", p.text().includes("Căn cứ: QĐ-TT/2026"), p.text().slice(0, 400));

// Sinh viên đang thực tập: timeline, đề cương, cảnh báo
p = await open("sv03");
check("sv03 timeline", p.text().includes("Các mốc bắt buộc") && p.text().includes("Nộp báo cáo giữa kỳ"), p.text().slice(0, 300));
check("sv03 risk flag shown", p.text().includes("Tổng giờ nhật ký"), p.text().slice(0, 300));
check("sv03 outline card", p.text().includes("Đề cương thực tập"), "");
await go(p, "#/logs");
check("sv03 logs", p.text().includes("Nhật ký tuần") && p.text().includes("Tuần 1"), p.text().slice(0, 300));
check("sv03 log attachment input", !!p.w.document.querySelector("[data-log-file]"), "");
await go(p, "#/assistant");
p.w.document.querySelector("#q").value = "Khi nào phải nộp đề cương?";
p.w.document.querySelector("#ask").requestSubmit();
await sleep(1500);
check("sv03 assistant answer w/ sources (SSE)", p.text().includes("Nguồn:") && p.text().includes("Điều 6"), p.text().slice(0, 500));
await go(p, "#/policies");
check("policies list", p.text().includes("QĐ-TT/2025") && p.text().includes("Đã bị thay thế"), p.text().slice(0, 300));
check("sv cannot upload policy", !p.w.document.querySelector("#pol-form"), "");
check("sv03 no js errors", p.errors.length === 0, p.errors.join(" | "));

// sv04: yêu cầu gia hạn hiển thị; form gia hạn có ô minh chứng
p = await open("sv04");
check("sv04 extension list", p.text().includes("Yêu cầu gia hạn"), p.text().slice(0, 300));
const extBtn = p.w.document.querySelector("[data-extend]");
extBtn.click();
await sleep(200);
check("sv04 extension form has evidence input", !!p.w.document.querySelector(`#ext-file-${extBtn.dataset.extend}`), "");

// Giảng viên: hàng chờ, sinh viên, chi tiết + audit, cảnh báo
p = await open("gv03");
check("gv03 queue outline + AI box", p.text().includes("Đề cương —") && p.text().includes("Gợi ý của AI"), p.text().slice(0, 400));
await go(p, "#/students");
check("gv03 student list (R7)", p.text().includes("Sinh viên phụ trách") && p.text().includes("Xuất Excel") && p.text().includes("% mốc"), p.text().slice(0, 200));
const riskSel = p.w.document.querySelector("#sf-risk");
riskSel.value = "any";
riskSel.dispatchEvent(new p.w.Event("change"));
await sleep(700);
check("gv03 risk filter", p.text().includes("Cảnh báo ×") || p.text().includes("Không có hồ sơ phù hợp"), p.text().slice(0, 300));
const link = p.w.document.querySelector('a[href^="#/internship/"]');
await go(p, link.getAttribute("href"));
check("gv03 internship detail + audit", p.text().includes("Lịch sử thao tác") && p.text().includes("status:"), p.text().slice(0, 300));
await go(p, "#/flags");
check("gv03 flags", p.text().includes("Sinh viên có cảnh báo") && p.text().includes("Tổng giờ nhật ký"), p.text().slice(0, 300));
check("gv03 no js errors", p.errors.length === 0, p.errors.join(" | "));

p = await open("gv02");
check("gv02 queue internship decision box", p.text().includes("Hồ sơ đăng ký —") && p.w.document.querySelector("[data-decide=internship]"), p.text().slice(0, 300));

// Quản trị viên
p = await open("admin");
check("admin home", p.text().includes("Quản trị") && p.text().includes("Mẫu mốc của đợt") && p.text().includes("Phân công giảng viên"), p.text().slice(0, 300));
check("admin template editor rows", p.w.document.querySelectorAll("#tpl-table tr[data-tpl]").length === 5, "");
p.w.document.querySelector("#tpl-add").click();
const last = [...p.w.document.querySelectorAll("#tpl-table tr[data-tpl]")].pop();
last.querySelector('[data-k="code"]').value = "khao_sat";
last.querySelector('[data-k="name"]').value = "Nộp phiếu khảo sát";
last.querySelector('[data-k="required_evidence"]').value = "other";
p.w.document.querySelector("#tpl-save").click();
await sleep(900);
check("admin template saved", p.w.document.querySelectorAll("#tpl-table tr[data-tpl]").length === 6 && p.text().includes("Mẫu mốc"), p.text().slice(0, 300));
await go(p, "#/students");
check("admin cohort-wide list (R7)", p.text().includes("Danh sách thực tập toàn khóa") && !!p.w.document.querySelector("#sf-lecturer"), p.text().slice(0, 300));
await go(p, "#/policies");
check("admin can upload policy", !!p.w.document.querySelector("#pol-form"), "");
check("admin no js errors", p.errors.length === 0, p.errors.join(" | "));

console.log(results.join("\n"));
console.log(`${results.filter((r) => r.startsWith("PASS")).length}/${results.length} passed`);
process.exit(0);
