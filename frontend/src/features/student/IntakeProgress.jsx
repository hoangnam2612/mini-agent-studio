import { useEffect, useState } from "react";
import Icon from "../../components/ui/Icon";

// Tiến trình xử lý file giấy tiếp nhận: các bước thật do backend báo qua SSE (/intake/extract/stream).
// Bước "OCR" chỉ xuất hiện khi file là bản scan/ảnh (backend gửi stage "ocr"), kèm thanh tiến độ theo trang.

const BASE = [
  ["upload", "Nhận file"],
  ["read", "Đọc nội dung"],
  ["extract", "Trích xuất các trường"],
];
const OCR_STEP = ["ocr", "Nhận dạng chữ trên ảnh (OCR)"];

export default function IntakeProgress({ progress }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, []);

  const steps = progress.ocr ? [BASE[0], BASE[1], OCR_STEP, BASE[2]] : BASE;
  const current = Math.max(steps.findIndex(([key]) => key === progress.stage), 0);
  const seconds = Math.floor((now - progress.startedAt) / 1000);
  const hasPages = progress.stage === "ocr" && progress.pages > 0;
  // Đang xử lý trang `page` nên tính nửa trang để thanh không đứng ở 0 khi trang đầu chưa xong
  const percent = hasPages ? Math.round(((progress.page - 0.5) / progress.pages) * 100) : null;

  return (
    <div className="intake-progress" role="status" aria-live="polite">
      <div className="intake-progress__head">
        <b>{progress.label}</b>
        <span className="muted small">{progress.fileName} · {seconds}s</span>
      </div>
      <ol className="steps">
        {steps.map(([key, text], idx) => {
          const state = idx < current ? "done" : idx === current ? "active" : "todo";
          return (
            <li key={key} className={`steps__item is-${state}`} aria-current={state === "active" ? "step" : undefined}>
              <span className="steps__dot">
                {state === "done" ? <Icon name="check" size={14} /> : state === "active" ? <span className="spinner" aria-hidden="true" /> : idx + 1}
              </span>
              <span>{text}{key === "ocr" && hasPages ? ` — trang ${progress.page}/${progress.pages}` : ""}</span>
            </li>
          );
        })}
      </ol>
      {percent !== null && (
        <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-label="Tiến độ nhận dạng chữ">
          <span style={{ width: `${percent}%` }} />
        </div>
      )}
      {!progress.ocr && progress.stage === "read" && seconds >= 4 && (
        <p className="hint">Đang đọc file, vui lòng chờ…</p>
      )}
      {progress.ocr && <p className="hint">Bản scan/ảnh cần nhận dạng chữ nên có thể mất vài chục giây (khoảng vài giây mỗi trang).</p>}
    </div>
  );
}
