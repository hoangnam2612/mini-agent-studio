// Tách từng màn wireframe thành file HTML tĩnh để import vào Figma (vd plugin html.to.design).
// Mỗi file chỉ có màn hình: không khung tên, không chú thích, không chấm đỏ, không khung thiết bị, không JS.
// Bố cục đóng cứng theo khổ: desktop 1440 px, mobile 390 px (không dùng container query).
// Chạy: node docs/wireframe/export-figma.mjs   (cần puppeteer-core trong tests/ui và Chrome/Edge)
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(here, "../../tests/ui/package.json"));
const puppeteer = require("puppeteer-core");
const BROWSER = process.env.BROWSER_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const OUT = join(here, "figma");

// 1. CSS: token + thành phần wireframe; tách khối mobile (@container) ra để áp thẳng cho file mobile
const src = readFileSync(join(here, "vin15-wireframe.html"), "utf8");
const css = src.match(/<style>([\s\S]*?)<\/style>/)[1];
const tokens = css.slice(css.indexOf(":root {"), css.indexOf("}", css.indexOf(":root {")) + 1);
const compStart = css.indexOf("/* ---------- thành phần wireframe");
const compEnd = css.indexOf("/* ---------- bìa");
let components = css.slice(compStart, compEnd);
const cq = components.indexOf("@container (max-width: 320px) {");
let depth = 0, end = cq;
for (let i = components.indexOf("{", cq); i < components.length; i++) {
  if (components[i] === "{") depth++;
  if (components[i] === "}" && --depth === 0) { end = i; break; }
}
const mobileRules = components.slice(components.indexOf("{", cq) + 1, end);
components = components.slice(0, cq) + components.slice(end + 1);

const VIEWPORTS = {
  desktop: { width: 1440, minHeight: 900, font: 16, extra: ".side .hide-d { display: none; }" },
  mobile: { width: 390, minHeight: 844, font: 14, extra: `.side .hide-m-only { display: none; }\n${mobileRules}` },
};

// 2. Lấy markup từng màn từ chính trang wireframe (hàm d() trong mảng SCREENS)
const browser = await puppeteer.launch({ executablePath: BROWSER, headless: true });
const page = await browser.newPage();
await page.goto(pathToFileURL(join(here, "export", "vin15-wireframe-print.html")).href, { waitUntil: "networkidle0" });
const screens = await page.evaluate(() => SCREENS.map((s) => ({ id: s.id, name: s.name, html: s.d() })));

const slug = (t) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D")
  .replace(/[^A-Za-z0-9]+/g, "-").replace(/^-|-$/g, "");
const clean = (html) => html.replace(/<span class="mk"[^>]*>[^<]*<\/span>/g, "");

rmSync(OUT, { recursive: true, force: true });
const written = [];
for (const [vp, v] of Object.entries(VIEWPORTS)) {
  mkdirSync(join(OUT, vp), { recursive: true });
  for (const s of screens) {
    const file = join(OUT, vp, `${s.id}-${slug(s.name)}.html`);
    writeFileSync(file, `<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=${v.width}">
<title>${s.id} ${s.name} — ${vp === "desktop" ? "Desktop 1440" : "Mobile 390"}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap">
<style>
${tokens}
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--paper); color: var(--ink); }
body { width: ${v.width}px; font-family: var(--f-ui); line-height: 1.45; }
.vp { position: relative; width: ${v.width}px; min-height: ${v.minHeight}px; font-size: ${v.font}px; overflow: hidden; }
.vp > .app, .vp > .split { min-height: ${v.minHeight}px; height: auto; }
h1, h2, h3 { margin: 0; }
${components}
${v.extra}
</style>
</head>
<body>
<div class="vp">${clean(s.html)}</div>
</body>
</html>
`);
    written.push(file);
  }
}

// 3. Chụp kiểm tra (tắt JS để chắc file không cần script)
const check = await browser.newPage();
await check.setJavaScriptEnabled(false);
mkdirSync(join(here, "export", "figma-check"), { recursive: true });
for (const f of written) {
  const vp = f.includes(`${"\\"}mobile${"\\"}`) || f.includes("/mobile/") ? VIEWPORTS.mobile : VIEWPORTS.desktop;
  await check.setViewport({ width: vp.width, height: vp.minHeight });
  await check.goto(pathToFileURL(f).href, { waitUntil: "networkidle0" });
  const over = await check.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  if (over > 0) console.log("overflow", over, "px:", f);
  await check.screenshot({ path: join(here, "export", "figma-check", f.split(/[\\/]/).slice(-2).join("-").replace(".html", ".png")), fullPage: true });
}
await browser.close();
console.log(`${written.length} file HTML (${screens.length} màn × desktop, mobile) → ${OUT}`);
