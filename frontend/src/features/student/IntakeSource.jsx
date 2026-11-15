import { useEffect, useMemo, useRef, useState } from "react";
import { FIELDS } from "../../lib/config";

// Khung xem file người dùng đã tải lên, tô sáng vùng mà từng giá trị gợi ý được lấy từ đó.
// - Bản scan/ảnh: ảnh từng trang + khung chữ nhật (toạ độ chuẩn hoá 0..1 từ OCR).
// - Mọi loại file: văn bản kèm đoạn được tô (offset trong document.text).
// `active` là tên trường đang chọn; bấm khung/đoạn tô hoặc dòng trong bảng để đổi.

const labelOf = (name) => (FIELDS.find((f) => f[0] === name) || [name, name])[1];

/** Cuộn trong khung xem (không cuộn cả trang) để phần tử hiện giữa khung. */
function scrollInside(container, el) {
  if (!container || !el) return;
  const c = container.getBoundingClientRect();
  const e = el.getBoundingClientRect();
  container.scrollTo({ top: container.scrollTop + (e.top - c.top) - c.height / 2 + e.height / 2, behavior: "smooth" });
}

export default function IntakeSource({ document: doc, fields, active, onSelect }) {
  const hasImage = doc.pages?.length > 0;
  const [tab, setTab] = useState(hasImage ? "image" : "text");
  const scroller = useRef(null);

  const located = useMemo(() => Object.entries(fields).filter(([, v]) => v.source), [fields]);

  // Đổi trường đang chọn → chuyển tới phần tử tương ứng trong tab hiện tại
  useEffect(() => {
    if (!active) return;
    const el = scroller.current?.querySelector(`[data-field="${active}"]`);
    scrollInside(scroller.current, el);
  }, [active, tab]);

  // Văn bản: chia thành đoạn thường / đoạn được tô (bỏ qua đoạn chồng lên đoạn trước)
  const segments = useMemo(() => {
    const spans = located
      .flatMap(([name, v]) => v.source.spans.map(([s, e]) => ({ name, s, e })))
      .sort((a, b) => a.s - b.s);
    const out = [];
    let pos = 0;
    spans.forEach(({ name, s, e }) => {
      if (s < pos) return;
      if (s > pos) out.push({ text: doc.text.slice(pos, s) });
      out.push({ text: doc.text.slice(s, e), name });
      pos = e;
    });
    if (pos < doc.text.length) out.push({ text: doc.text.slice(pos) });
    return out;
  }, [located, doc.text]);

  return (
    <div className="src">
      <div className="src__bar">
        <b>{hasImage ? "File bạn đã tải lên" : "Nội dung file"}</b>
        {hasImage && (
          <div className="src__tabs" role="tablist" aria-label="Chế độ xem">
            <button type="button" role="tab" aria-selected={tab === "image"} className={tab === "image" ? "is-on" : ""} onClick={() => setTab("image")}>Bản gốc</button>
            <button type="button" role="tab" aria-selected={tab === "text"} className={tab === "text" ? "is-on" : ""} onClick={() => setTab("text")}>Văn bản nhận dạng</button>
          </div>
        )}
      </div>

      <div className="src__scroll" ref={scroller} tabIndex={0} aria-label="Nội dung file với các vùng được tô sáng">
        {tab === "image" && doc.pages.map((page) => (
          <figure className="src-page" key={page.index}>
            <figcaption className="small muted">Trang {page.index + 1}/{doc.pages.length}</figcaption>
            <div className="src-page__frame">
              <img src={page.image} alt={`Trang ${page.index + 1} của file đã tải lên`} width={page.width} height={page.height} />
              {located.flatMap(([name, v]) => (v.source.boxes || []).filter((b) => b.page === page.index).map((b, idx) => (
                <button
                  type="button" key={`${name}-${idx}`}
                  data-field={idx === 0 ? name : undefined}
                  className={`src-box ${active === name ? "is-active" : ""}`}
                  style={{ left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` }}
                  aria-label={`${labelOf(name)}: ${v.raw || v.value}`}
                  onClick={() => onSelect(name)}
                >
                  {active === name && idx === 0 && <span className="src-box__tag">{labelOf(name)}</span>}
                </button>
              )))}
            </div>
          </figure>
        ))}

        {tab === "text" && (
          <pre className="src-text">
            {segments.map((seg, idx) => (seg.name
              ? (
                <mark
                  key={idx} data-field={seg.name} title={labelOf(seg.name)}
                  className={active === seg.name ? "is-active" : ""} onClick={() => onSelect(seg.name)}
                >{seg.text}</mark>
              )
              : <span key={idx}>{seg.text}</span>))}
          </pre>
        )}
      </div>
      <p className="hint">
        {tab === "image"
          ? "Khung sáng là chỗ hệ thống đọc ra giá trị. Bấm khung hoặc bấm “Xem trong file” ở bảng để đối chiếu."
          : "Đoạn được tô là chỗ giá trị được lấy ra. Đây cũng là chữ mà hệ thống đọc được — nếu sai chữ số thì nên nhập tay."}
        {doc.truncated && " (Chỉ hiển thị phần đầu văn bản.)"}
      </p>
    </div>
  );
}
