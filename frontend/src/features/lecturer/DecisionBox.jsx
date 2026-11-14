import { useState } from "react";
import { useToast } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { Button, Field } from "../../components/ui";

// Hộp quyết định của giảng viên (duyệt / yêu cầu chỉnh sửa / từ chối) — dùng cho hồ sơ, đề cương, gia hạn.

const PATHS = {
  internship: (id) => `/internships/${id}/decision`,
  outline: (id) => `/outlines/${id}/decision`,
  extension: (id) => `/extensions/${id}/decision`,
};

const OPTIONS = {
  extension: [["approved", "Chấp nhận gia hạn", "ok"], ["rejected", "Từ chối", "danger"]],
  default: [["approved", "Duyệt", "ok"], ["revision_requested", "Yêu cầu chỉnh sửa", ""], ["rejected", "Từ chối", "danger"]],
};

export default function DecisionBox({ kind, id, version, onDone }) {
  const { run } = useToast();
  const [reason, setReason] = useState("");

  const decide = async (decision) => {
    const body = { decision, reason };
    if (version != null) body.version = version;
    await run(() => api("POST", PATHS[kind](id), body), "Đã ghi nhận quyết định");
    onDone();
  };

  return (
    <div className="decision">
      <Field as="textarea" id={`reason-${kind}-${id}`} style={{ minHeight: 72 }}
        label={kind === "extension" ? "Lý do / nhận xét (bắt buộc)" : "Nhận xét (bắt buộc khi yêu cầu sửa hoặc từ chối)"}
        value={reason} onChange={(e) => setReason(e.target.value)} />
      <div className="form-actions" style={{ marginTop: 16 }}>
        {(OPTIONS[kind] || OPTIONS.default).map(([d, text, variant]) => (
          <Button key={d} variant={variant} onClick={() => decide(d)}>{text}</Button>
        ))}
      </div>
    </div>
  );
}
