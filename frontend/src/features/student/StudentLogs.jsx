import { useState } from "react";
import { useToast } from "../../context/ToastContext";
import { useAsync } from "../../hooks/useAsync";
import { api, formData } from "../../lib/api";
import { Async, Badge, Button, Card, CardHead, Empty, Field, PageHead } from "../../components/ui";
import { EvidenceLink } from "../shared/EvidenceLink";

// Nhật ký tuần của sinh viên.

async function loadLogs() {
  const list = await api("GET", "/internships");
  const internship = list[0];
  if (!internship || !["approved", "in_progress", "completed"].includes(internship.status)) return { internship: null };
  return { internship, logs: await api("GET", `/internships/${internship.id}/logs`) };
}

export default function StudentLogs() {
  const state = useAsync(loadLogs);
  return (
    <>
      <PageHead title="Nhật ký tuần" />
      <Async state={state}>
        {(d) => d.internship
          ? <LogsBody internship={d.internship} logs={d.logs} reload={state.reload} />
          : <Empty>Nhật ký mở sau khi hồ sơ đăng ký được duyệt.</Empty>}
      </Async>
    </>
  );
}

function LogsBody({ internship: i, logs, reload }) {
  const { run } = useToast();
  const total = logs.reduce((s, l) => s + l.hours, 0);
  const next = logs.length ? Math.max(...logs.map((l) => l.week_no)) + 1 : 1;
  const [form, setForm] = useState({ week_no: next, hours: "", content: "", difficulties: "" });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const save = async () => {
    await run(() => api("POST", `/internships/${i.id}/logs`, { ...form, week_no: Number(form.week_no), hours: Number(form.hours) }), "Đã ghi nhật ký");
    setForm({ week_no: next + 1, hours: "", content: "", difficulties: "" });
    reload();
  };
  const attach = async (logId, file) => {
    if (!file) return;
    await run(() => api("POST", `/logs/${logId}/attachments`, formData({ file }), true), "Đã đính kèm file");
    reload();
  };
  const resend = async (l) => {
    const content = prompt("Nội dung nhật ký đã bổ sung:", l.content);
    if (!content) return;
    await run(() => api("PATCH", `/logs/${l.id}`, { week_no: l.week_no, content, difficulties: l.difficulties, hours: l.hours }), "Đã gửi lại");
    reload();
  };

  return (
    <>
      <p className="muted" style={{ marginTop: -12 }}>
        Tổng {total} giờ · quy chế: trung bình {i.mode === "part_time" ? 16 : 32} giờ/tuần (QĐ-TT/2026 · Điều 8 / Khoản 2)
      </p>

      {i.status !== "completed" && (
        <Card>
          <CardHead title="Ghi nhật ký mới" />
          <div className="grid2">
            <Field id="l-week" label="Tuần" type="number" min="1" value={form.week_no} onChange={set("week_no")} />
            <Field id="l-hours" label="Số giờ" type="number" min="0" max="80" step="0.5" value={form.hours} onChange={set("hours")} />
          </div>
          <div className="field-stack" style={{ marginTop: 16 }}>
            <Field id="l-content" as="textarea" label="Công việc đã làm" value={form.content} onChange={set("content")} />
            <Field id="l-diff" as="textarea" label="Khó khăn (nếu có)" style={{ minHeight: 64 }} value={form.difficulties} onChange={set("difficulties")} />
          </div>
          <div className="form-actions"><Button variant="primary" onClick={save}>Ghi nhật ký</Button></div>
        </Card>
      )}

      <Card>
        <CardHead title="Các tuần đã ghi" />
        <div className="table-wrap">
          <table>
            <thead><tr><th>Tuần</th><th>Nội dung</th><th>Giờ</th><th>Trạng thái</th></tr></thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id}>
                  <td>{l.week_no}</td>
                  <td>
                    <div className="pre">{l.content}</div>
                    {l.comment && <div className="small muted">GV: {l.comment}</div>}
                    {l.attachments.length > 0 && <div className="small">Đính kèm: {l.attachments.map((e) => <EvidenceLink key={e.id} id={e.id}>{e.filename}</EvidenceLink>)}</div>}
                    {l.review_status !== "accepted" && (
                      <label className="link-btn small" style={{ display: "inline-block", marginTop: 4 }}>
                        Đính kèm file <input type="file" accept=".pdf,.docx,.png,.jpg,.jpeg" hidden onChange={(e) => attach(l.id, e.target.files[0])} />
                      </label>
                    )}
                    {l.review_status === "returned" && <div><button className="link-btn" onClick={() => resend(l)}>Sửa & gửi lại</button></div>}
                  </td>
                  <td>{l.hours}</td>
                  <td><Badge status={l.review_status} /></td>
                </tr>
              ))}
              {logs.length === 0 && <tr><td colSpan="4" className="muted">Chưa có nhật ký.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
