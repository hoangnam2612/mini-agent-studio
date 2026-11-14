// NFR-3: mở từng màn hình trong Chrome/Edge thật (headless) ở viewport điện thoại 390×844,
// kiểm tra không tràn ngang, không lỗi JS, và chụp ảnh vào tests/ui/screens/.
// Dùng: server đang chạy (mặc định https://localhost qua Caddy), `npm i` trong tests/ui, rồi `node mobile-check.mjs`.
import { mkdirSync } from "node:fs";
import puppeteer from "puppeteer-core";

const BASE = process.env.BASE_URL || "https://localhost";
const BROWSER = process.env.BROWSER_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const OUT = new URL("./screens/", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");
mkdirSync(OUT, { recursive: true });

const pages = [
  ["login", null, "#/"],
  ["sv03-home", "sv03", "#/"],
  ["sv03-logs", "sv03", "#/logs"],
  ["sv03-assistant", "sv03", "#/assistant"],
  ["sv04-home", "sv04", "#/"],
  ["gv03-queue", "gv03", "#/"],
  ["gv03-flags", "gv03", "#/flags"],
  ["gv01-students", "gv01", "#/students"],
  ["admin-home", "admin", "#/"],
  ["admin-summary", "admin", "#/students"],
  ["policies", "sv03", "#/policies"],
];

const browser = await puppeteer.launch({ executablePath: BROWSER, headless: true, args: ["--ignore-certificate-errors"] });
const results = [];
for (const [name, user, hash] of pages) {
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto(BASE + "/", { waitUntil: "networkidle0" });
  if (user) {
    const token = await page.evaluate(async (u) => {
      const r = await fetch("/api/v1/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: u, password: "demo123" }) });
      return (await r.json()).token;
    }, user);
    await page.evaluate((t, h) => { localStorage.setItem("vin15_token", t); location.hash = h; }, token, hash);
    await page.reload({ waitUntil: "networkidle0" });
  }
  await new Promise((r) => setTimeout(r, 400));
  const m = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, inner: window.innerWidth }));
  await page.screenshot({ path: `${OUT}${name}.png`, fullPage: true });
  const ok = m.scroll <= m.inner && errors.length === 0;
  results.push(`${ok ? "PASS" : "FAIL"} ${name}: scrollWidth=${m.scroll} innerWidth=${m.inner}${errors.length ? " errors=" + errors.join(" | ") : ""}`);
  await page.close();
}
await browser.close();
console.log(results.join("\n"));
console.log(`${results.filter((r) => r.startsWith("PASS")).length}/${results.length} passed`);
