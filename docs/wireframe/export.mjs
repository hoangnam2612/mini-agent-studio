// Xuất wireframe: bản HTML in được (có doctype), PDF A4 ngang, và PNG từng tờ.
// Chạy: cd tests/ui && npm i   (lấy puppeteer-core)  rồi  node ../../docs/wireframe/export.mjs
// Cần Chrome hoặc Edge; đặt BROWSER_PATH nếu không ở vị trí mặc định.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(here, "../../tests/ui/package.json"));
const puppeteer = require("puppeteer-core");
const BROWSER = process.env.BROWSER_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";

const out = join(here, "export");
mkdirSync(join(out, "png"), { recursive: true });
const src = readFileSync(join(here, "vin15-wireframe.html"), "utf8");
const printable = `<!doctype html>\n<html lang="vi">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n</head>\n<body>\n${src}\n</body>\n</html>\n`;
const printPath = join(out, "vin15-wireframe-print.html");
writeFileSync(printPath, printable);

const browser = await puppeteer.launch({ executablePath: BROWSER, headless: true });
const page = await browser.newPage();
await page.setViewport({ width: 1200, height: 900, deviceScaleFactor: 2 });
await page.goto(pathToFileURL(printPath).href, { waitUntil: "networkidle0" });
await page.evaluate(() => document.fonts.ready);

// PDF toàn bộ (dùng CSS @page A4 ngang của trang)
await page.emulateMediaType("print");
await page.evaluate(() => window.dispatchEvent(new Event("beforeprint")));
await page.pdf({ path: join(out, "vin15-wireframe.pdf"), preferCSSPageSize: true, printBackground: true });
const cuts = await page.evaluate(() => [...document.querySelectorAll(".sheet")].flatMap((s) =>
  [...s.querySelectorAll(".dev.cut")].map((d) => `${s.id}:${d.classList.contains("dev--phone") ? "mobile" : "desktop"}`)));

// PNG từng tờ ở kích thước in (283×196 mm ≈ 1070×741 px @96dpi)
const ids = await page.evaluate(() => [...document.querySelectorAll(".sheet")].map((s) => s.id));
for (const id of ids) {
  const el = await page.$(`#${id}`);
  const name = await page.evaluate((e) => e.dataset.title, el);
  const safe = `${id}-${name}`.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").replace(/[^A-Za-z0-9]+/g, "-").replace(/-+$/, "");
  await el.screenshot({ path: join(out, "png", `${safe}.png`) });
}
await browser.close();
console.log(`PDF: ${ids.length} tờ · PNG: ${ids.length} file · khung bị cắt khi in: ${cuts.length ? cuts.join(", ") : "không có"}`);
