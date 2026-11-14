import { useAsync } from "../../hooks/useAsync";
import { api } from "../../lib/api";
import { FIELDS } from "../../lib/config";
import { fmtDate } from "../../lib/format";
import { AiBox, AiTag, Async, Avatar, Badge, Card, Empty, PageHead } from "../../components/ui";
import { EvidenceLink } from "../shared/EvidenceLink";
import DecisionBox from "./DecisionBox";

// Hàng chờ phê duyệt của giảng viên: hồ sơ, đề cương, gia hạn.

export default function LecturerQueue() {
  const state = useAsync(() => api("GET", "/approvals/queue"));
  return (
    <Async state={state}>
      {(q) => {
        const count = q.internships.length + q.outlines.length + q.extensions.length;
        return (
          <>
            <PageHead title="Hàng chờ phê duyệt" subtitle={count ? `${count} mục đang chờ bạn xử lý` : undefined} />
            {count === 0 && <Empty>Không có mục nào chờ duyệt.</Empty>}
            {q.internships.map((i) => <InternshipCard key={`i${i.id}`} i={i} reload={state.reload} />)}
            {q.outlines.map((o) => <OutlineCard key={`o${o.id}`} o={o} reload={state.reload} />)}
            {q.extensions.map((e) => <ExtensionCard key={`e${e.id}`} e={e} reload={state.reload} />)}
          </>
        );
      }}
    </Async>
  );
}

function Header({ name, subtitle, right }) {
  return (
    <div className="row spread">
      <div className="who"><Avatar name={name} /><div><div style={{ fontWeight: 700, fontSize: "1.05rem" }}>{name}</div><div className="small muted">{subtitle}</div></div></div>
      {right}
    </div>
  );
}

function fieldValue(i, n) {
  if (n.endsWith("date")) return fmtDate(i[n]);
  if (n === "mode") return i[n] === "part_time" ? "Bán thời gian" : "Toàn thời gian";
  return i[n] || "—";
}

function InternshipCard({ i, reload }) {
  const ai = new Set(i.ai_fields || []);
  return (
    <Card>
      <Header name={i.student.full_name} subtitle="Hồ sơ đăng ký" right={<Badge status={i.status} />} />
      <dl className="kv">
        {FIELDS.map(([n, l]) => (
          <div key={n}><dt>{l} {ai.has(n) && <AiTag />}</dt><dd>{fieldValue(i, n)}</dd></div>
        ))}
      </dl>
      <DecisionBox kind="internship" id={i.id} version={i.version} onDone={reload} />
    </Card>
  );
}

export function OutlineAi({ s }) {
  if (!s) return <p className="muted small">Không có gợi ý AI cho đề cương này.</p>;
  return (
    <AiBox label={s.label}>
      <p>{s.summary}</p>
      {s.uncovered_outcomes.length ? (
        <>
          <p className="small"><b>Chuẩn đầu ra chưa thấy nhắc tới:</b></p>
          <ul className="small">{s.uncovered_outcomes.map((c) => <li key={c.code}>{c.code} — {c.text}</li>)}</ul>
        </>
      ) : <p className="small">Đề cương có nhắc tới mọi chuẩn đầu ra học phần.</p>}
    </AiBox>
  );
}

function OutlineCard({ o, reload }) {
  return (
    <Card>
      <Header name={o.internship.student.full_name} subtitle={`Đề cương thực tập · phiên bản ${o.version}`} />
      <p className="pre" style={{ margin: "16px 0" }}>{o.content}</p>
      <OutlineAi s={o.ai_summary} />
      <DecisionBox kind="outline" id={o.id} version={o.version} onDone={reload} />
    </Card>
  );
}

function ExtensionCard({ e, reload }) {
  return (
    <Card>
      <Header name={e.student.full_name} subtitle={`Xin gia hạn · ${e.milestone.name}`}
        right={<div>{fmtDate(e.previous_due_date)} → <b>{fmtDate(e.requested_due_date)}</b></div>} />
      <p className="pre" style={{ margin: "16px 0" }}>{e.reason}</p>
      {e.evidence_id && <p className="small">Minh chứng kèm theo: <EvidenceLink id={e.evidence_id}>mở file</EvidenceLink></p>}
      {e.ai_summary && (
        <AiBox label={e.ai_summary.label}>
          <p>{e.ai_summary.summary}</p>
          {e.ai_summary.related_clauses.map((c, idx) => (
            <details key={idx}><summary className="small">{c.label}</summary><p className="pre small">{c.text}</p></details>
          ))}
        </AiBox>
      )}
      <DecisionBox kind="extension" id={e.id} onDone={reload} />
    </Card>
  );
}
