import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useAsync } from "../../hooks/useAsync";
import { api } from "../../lib/api";
import { SEVERITY } from "../../lib/config";
import { fmtDate } from "../../lib/format";
import { Alert, Async, Badge, Button, Card, CardHead, PageHead } from "../../components/ui";
import RegistrationForm from "./RegistrationForm";
import Timeline, { currentMilestone } from "./Timeline";
import Icon from "../../components/ui/Icon";
import Outline from "./Outline";
import ExtensionList from "./ExtensionList";

// Trang chủ sinh viên: hồ sơ, mốc, đề cương, gia hạn.

async function loadHome() {
  const list = await api("GET", "/internships");
  if (!list.length) return { internship: null };
  const internship = await api("GET", `/internships/${list[0].id}`);
  const [flags, extensions] = await Promise.all([
    api("GET", "/risk-flags"),
    api("GET", `/internships/${internship.id}/extensions`),
  ]);
  return { internship, flags, extensions };
}

/** Dòng nổi bật "việc tiếp theo" — chỉ hiện khi hồ sơ đã có mốc. */
function NextStop({ internship: i }) {
  if (!i.milestones.length) return null;
  const m = currentMilestone(i);
  if (!m) {
    return (
      <div className="nextstop nextstop--done">
        <span className="nextstop__icon"><Icon name="check" /></span>
        <div className="nextstop__text">Bạn đã hoàn thành mọi mốc bắt buộc.</div>
      </div>
    );
  }
  const left = m.days_left >= 0 ? `còn ${m.days_left} ngày` : `quá hạn ${-m.days_left} ngày`;
  return (
    <div className="nextstop">
      <span className="nextstop__icon"><Icon name="flag" /></span>
      <div className="nextstop__text">Việc tiếp theo: {m.name} <span>· hạn {fmtDate(m.due_date)} ({left})</span></div>
    </div>
  );
}

export default function StudentHome() {
  const state = useAsync(loadHome);
  return <Async state={state}>{(data) => <Home data={data} reload={state.reload} />}</Async>;
}

function Home({ data, reload }) {
  const { me, config } = useAuth();
  const { run } = useToast();
  const { internship: i, flags, extensions } = data;
  const firstName = me.full_name.trim().split(/\s+/).pop();

  if (!i) {
    const c = config.cohort;
    return (
      <>
        <PageHead title={`Xin chào, ${firstName}`} subtitle={`Đợt thực tập: ${c.name}`} />
        <Card>
          <CardHead title="Bạn chưa có hồ sơ thực tập" />
          <p>Tạo hồ sơ nháp để bắt đầu đăng ký. Khung thời gian: {fmtDate(c.start_window)} – {fmtDate(c.end_window)} · tối thiểu {c.min_weeks} tuần.</p>
          <Button variant="primary" onClick={async () => { await run(() => api("POST", "/internships", {}), "Đã tạo hồ sơ nháp"); reload(); }}>
            Tạo hồ sơ đăng ký
          </Button>
        </Card>
      </>
    );
  }

  const editable = ["draft", "revision_requested"].includes(i.status);
  const started = ["approved", "in_progress", "completed"].includes(i.status);

  return (
    <>
      <PageHead title={`Xin chào, ${firstName}`} subtitle={`Đợt ${config.cohort.name} · GV phụ trách: ${i.lecturer?.full_name || "chưa phân công"}`} />

      <NextStop internship={i} />

      {i.decision_reason && (
        <Alert tone={i.status === "revision_requested" ? "warn" : "ok"} title={i.status === "revision_requested" ? "Giảng viên yêu cầu chỉnh sửa hồ sơ" : "Nhận xét của giảng viên"}>
          {i.decision_reason}
        </Alert>
      )}
      {flags.map((f) => (
        <Alert key={f.id} tone={SEVERITY[f.severity]?.[1] === "bad" ? "bad" : "warn"} title={SEVERITY[f.severity]?.[0]}>{f.reason}</Alert>
      ))}

      <RegistrationForm key={i.version} internship={i} editable={editable} reload={reload} status={<Badge status={i.status} />} />

      {i.milestones.length > 0 && (
        <Card>
          <CardHead title="Các mốc bắt buộc" />
          <Timeline internship={i} reload={reload} />
        </Card>
      )}
      {started && <Outline internship={i} reload={reload} />}
      {extensions.length > 0 && <ExtensionList extensions={extensions} reload={reload} />}
    </>
  );
}
