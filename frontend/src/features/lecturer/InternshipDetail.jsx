import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useAsync } from "../../hooks/useAsync";
import { api } from "../../lib/api";
import { fmtDate, fmtDateTime } from "../../lib/format";
import { Async, Badge, Button, Card, CardHead, PageHead } from "../../components/ui";
import Icon from "../../components/ui/Icon";
import { EvidenceLink } from "../shared/EvidenceLink";

// Chi tiết một hồ sơ thực tập (GV / QTV). QTV chỉ xem — duyệt thuộc GV phụ trách (HITL).

export default function InternshipDetail() {
  const { id } = useParams();
  const { me } = useAuth();
  const canReview = me.role === "lecturer";
  const state = useAsync(async () => {
    const [i, logs, audit] = await Promise.all([
      api("GET", `/internships/${id}`), api("GET", `/internships/${id}/logs`), api("GET", `/internships/${id}/audit`),
    ]);
    return { i, logs, audit };
  }, [id]);

  return (
    <Async state={state}>
      {({ i, logs, audit }) => (
        <>
          <PageHead title={i.student.full_name} subtitle={`${i.company_name || "—"} · ${i.position || "—"} · ${fmtDate(i.start_date)} – ${fmtDate(i.end_date)}`}>
            <div className="row"><Badge status={i.status} /><Link className="btn btn--sm" to="/students">← Danh sách</Link></div>
          </PageHead>

          {i.milestones.length > 0 && (
            <Card>
              <CardHead title="Các mốc" />
              <ol className="timeline">
                {i.milestones.map((m) => <MilestoneRow key={m.id} m={m} canReview={canReview} reload={state.reload} />)}
              </ol>
            </Card>
          )}

          {i.outline && (
            <Card>
              <CardHead title="Đề cương"><Badge status={i.outline.status} /></CardHead>
              <p className="pre">{i.outline.content}</p>
              {i.outline.reason && <p className="small muted">Nhận xét: {i.outline.reason}</p>}
            </Card>
          )}

          <Card>
            <CardHead title={`Nhật ký (${logs.reduce((s, l) => s + l.hours, 0)} giờ)`} />
            <div className="table-wrap">
              <table>
                <thead><tr><th>Tuần</th><th>Nội dung</th><th>Giờ</th><th>Trạng thái</th></tr></thead>
                <tbody>
                  {logs.map((l) => <LogRow key={l.id} l={l} canReview={canReview} reload={state.reload} />)}
                  {logs.length === 0 && <tr><td colSpan="4" className="muted">Chưa có nhật ký.</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>

          <Card>
            <CardHead title="Lịch sử thao tác (audit)" />
            <div className="table-wrap">
              <table>
                <thead><tr><th>Thời điểm</th><th>Người</th><th>Đối tượng</th><th>Hành động</th><th>Lý do</th></tr></thead>
                <tbody>
                  {audit.map((a, idx) => (
                    <tr key={idx} className="small">
                      <td>{fmtDateTime(a.at)}</td><td>{a.actor}</td><td>{a.entity} #{a.entity_id ?? ""}</td><td>{a.action}</td><td>{a.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </Async>
  );
}

/** Ô nhận xét + 2 nút Chấp nhận / Trả lại dùng chung cho mốc và nhật ký. */
function ReviewInline({ path, rejectDecision, onDone, accepted = "accepted" }) {
  const { run } = useToast();
  const [comment, setComment] = useState("");
  const send = async (decision) => { await run(() => api("POST", path, { decision, comment }), "Đã cập nhật"); onDone(); };
  return (
    <div className="row" style={{ marginTop: 8 }}>
      <input className="input" style={{ flex: 1, minWidth: 180 }} placeholder="Nhận xét (bắt buộc khi trả lại)" aria-label="Nhận xét" value={comment} onChange={(e) => setComment(e.target.value)} />
      <Button size="sm" variant="ok" onClick={() => send(accepted)}>Chấp nhận</Button>
      <Button size="sm" variant="danger" onClick={() => send(rejectDecision)}>Trả lại</Button>
    </div>
  );
}

function MilestoneRow({ m, canReview, reload }) {
  return (
    <li className={`timeline__item ${m.status}`}>
      <div className="timeline__rail">
        <span className="timeline__dot">{m.status === "accepted" && <Icon name="check" size={14} strokeWidth={3} />}</span>
        <span className="timeline__line" />
      </div>
      <div className="timeline__body">
        <div className="row spread"><b>{m.name}</b><Badge status={m.status} /></div>
        <div className="small muted">Hạn {fmtDate(m.due_date)}</div>
        {m.evidence.length > 0 && <div className="small">Minh chứng: {m.evidence.map((e) => <EvidenceLink key={e.id} id={e.id}>{e.filename}</EvidenceLink>)}</div>}
        {canReview && m.status === "submitted" && !m.linked_to && (
          <ReviewInline path={`/milestones/${m.id}/review`} rejectDecision="rejected" onDone={reload} />
        )}
      </div>
    </li>
  );
}

function LogRow({ l, canReview, reload }) {
  return (
    <tr>
      <td>{l.week_no}</td>
      <td>
        <div className="pre">{l.content}</div>
        {l.difficulties && <div className="small muted">Khó khăn: {l.difficulties}</div>}
        {canReview && l.review_status === "pending"
          ? <ReviewInline path={`/logs/${l.id}/review`} rejectDecision="returned" onDone={reload} />
          : l.comment && <div className="small">GV: {l.comment}</div>}
      </td>
      <td>{l.hours}</td>
      <td><Badge status={l.review_status} /></td>
    </tr>
  );
}
