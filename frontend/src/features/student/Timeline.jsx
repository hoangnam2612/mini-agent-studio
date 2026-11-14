import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { api, formData } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import { Badge, Button, Citation, Field } from "../../components/ui";
import Icon from "../../components/ui/Icon";
import { EvidenceLink } from "../shared/EvidenceLink";

// Các mốc bắt buộc + nộp minh chứng + xin gia hạn.

export default function Timeline({ internship: i, reload }) {
  return (
    <ol className="timeline">
      {i.milestones.map((m, idx) => <Milestone key={m.id} m={m} index={idx} current={m.id === currentMilestone(i)?.id} reload={reload} />)}
    </ol>
  );
}

/** Chặng hiện tại = mốc đầu tiên chưa được chấp nhận. */
export const currentMilestone = (i) => i.milestones.find((m) => m.status !== "accepted");

function Milestone({ m, index, current, reload }) {
  const { me, config } = useAuth();
  const { run } = useToast();
  const types = config.evidence_types;
  const canAct = me.role === "student" && ["pending", "overdue", "rejected"].includes(m.status) && !m.linked_to;
  const [evidenceType, setEvidenceType] = useState(m.required_evidence[0] || Object.keys(types)[0]);
  const [extending, setExtending] = useState(false);
  const left = m.status === "accepted" ? "" : m.days_left >= 0 ? `còn ${m.days_left} ngày` : `quá ${-m.days_left} ngày`;

  const upload = async (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    await run(() => api("POST", `/milestones/${m.id}/evidence`, formData({ file, evidence_type: evidenceType }), true), "Đã tải minh chứng");
    reload();
  };
  const submit = async () => { await run(() => api("POST", `/milestones/${m.id}/submit`), "Đã nộp mốc"); reload(); };

  return (
    <li className={`timeline__item ${m.status} ${current ? "is-current" : ""}`} aria-current={current ? "step" : undefined}>
      <div className="timeline__rail">
        <span className="timeline__dot">{m.status === "accepted" ? <Icon name="check" size={18} strokeWidth={3} /> : index + 1}</span>
        <span className="timeline__line" />
      </div>
      <div className="timeline__body">
        <div className="row spread"><span><b>{m.name}</b>{current && <span className="timeline__here">Chặng tiếp theo</span>}</span><Badge status={m.status} /></div>
        <div className="small muted">
          Hạn {fmtDate(m.due_date)}{left && ` · ${left}`}{m.linked_to && " · cập nhật theo đề cương"}
        </div>
        {m.required_evidence.length > 0 && (
          <div className="small">Minh chứng yêu cầu: {m.required_evidence.map((t) => types[t] || t).join(", ")}</div>
        )}
        {m.evidence.length > 0 && (
          <div className="small">Đã tải: {m.evidence.map((e) => <EvidenceLink key={e.id} id={e.id}>{e.filename}</EvidenceLink>)}</div>
        )}
        {m.comment && <div className="small">Nhận xét GV: {m.comment}</div>}
        <Citation c={m.citation} />

        {canAct && (
          <div className="row" style={{ marginTop: 10 }}>
            <select className="input" style={{ width: "auto" }} value={evidenceType} onChange={(e) => setEvidenceType(e.target.value)} aria-label="Loại minh chứng">
              {Object.entries(types).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <label className="btn btn--sm">
              <Icon name="upload" size={16} />Tải minh chứng
              <input type="file" accept=".pdf,.docx,.png,.jpg,.jpeg" onChange={upload} hidden />
            </label>
            <Button variant="primary" size="sm" onClick={submit}>Nộp mốc</Button>
            <Button size="sm" onClick={() => setExtending((v) => !v)}>Xin gia hạn</Button>
          </div>
        )}
        {extending && <ExtensionForm m={m} onDone={() => { setExtending(false); reload(); }} />}
      </div>
    </li>
  );
}

function ExtensionForm({ m, onDone }) {
  const { run } = useToast();
  const [date, setDate] = useState("");
  const [reason, setReason] = useState("");
  const [file, setFile] = useState(null);

  const send = async () => {
    const body = { requested_due_date: date, reason };
    if (file) {
      const ev = await run(() => api("POST", `/milestones/${m.id}/evidence`, formData({ file, evidence_type: "other" }), true));
      body.evidence_id = ev.id;
    }
    await run(() => api("POST", `/milestones/${m.id}/extensions`, body), "Đã gửi yêu cầu gia hạn");
    onDone();
  };

  return (
    <div className="panel">
      <h3>Xin gia hạn: {m.name}</h3>
      <p className="small muted">Hạn hiện tại {fmtDate(m.due_date)} · mỗi lần không quá 14 ngày (QĐ-TT/2026 · Điều 10 / Khoản 2). Giảng viên phụ trách sẽ quyết định.</p>
      <div className="field-stack">
        <Field id={`ext-d-${m.id}`} label="Hạn mới đề xuất" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        <Field id={`ext-r-${m.id}`} as="textarea" label="Lý do" value={reason} onChange={(e) => setReason(e.target.value)} />
        <Field id={`ext-f-${m.id}`} type="file" label="Minh chứng cho lý do (tùy chọn: giấy khám bệnh, email của doanh nghiệp…)"
          accept=".pdf,.docx,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files[0] || null)} />
        <div><Button variant="primary" onClick={send}>Gửi yêu cầu</Button></div>
      </div>
    </div>
  );
}
