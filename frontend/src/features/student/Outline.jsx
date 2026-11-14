import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { Badge, Button, Card, Field } from "../../components/ui";

// Đề cương thực tập (sinh viên nộp / nộp lại).

export default function Outline({ internship: i, reload }) {
  const { me } = useAuth();
  const { run } = useToast();
  const o = i.outline;
  const canSubmit = me.role === "student" && (!o || ["revision_requested", "rejected"].includes(o.status));
  const [text, setText] = useState(o?.content || "");

  const send = async () => {
    await run(() => api("POST", `/internships/${i.id}/outline`, { content: text }), "Đã nộp đề cương");
    reload();
  };

  return (
    <Card>
      <div className="card__head">
        <h2>Đề cương thực tập</h2>
        {o && <Badge status={o.status} />}
      </div>
      {o?.reason && <p className={o.status === "approved" ? "muted" : "errors"} style={{ paddingLeft: 0, listStyle: "none" }}>Nhận xét GV: {o.reason}</p>}
      {canSubmit ? (
        <>
          <Field as="textarea" id="outline-text" label="Mục tiêu, nhiệm vụ, kế hoạch theo tuần, kết quả dự kiến (tối thiểu 50 ký tự)"
            style={{ minHeight: 180 }} value={text} onChange={(e) => setText(e.target.value)} />
          <div className="form-actions"><Button variant="primary" onClick={send}>Nộp đề cương</Button></div>
        </>
      ) : (
        <p className="pre">{o?.content}</p>
      )}
    </Card>
  );
}
