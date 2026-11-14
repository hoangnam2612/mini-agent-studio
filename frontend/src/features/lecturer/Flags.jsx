import { useState } from "react";
import { Link } from "react-router-dom";
import { useToast } from "../../context/ToastContext";
import { useAsync } from "../../hooks/useAsync";
import { api } from "../../lib/api";
import { SEVERITY } from "../../lib/config";
import { fmtDate } from "../../lib/format";
import { Async, Badge, Button, Card, Empty, PageHead } from "../../components/ui";

// Cảnh báo rủi ro do tác tử giám sát sinh ra.

export default function Flags() {
  const state = useAsync(() => api("GET", "/risk-flags"));
  return (
    <>
      <PageHead title="Sinh viên có cảnh báo" subtitle="Cảnh báo do tác tử giám sát sinh ra theo luật; tác tử không thay đổi trạng thái hồ sơ." />
      <Async state={state}>
        {(flags) => flags.length === 0
          ? <Empty>Không có cảnh báo đang mở.</Empty>
          : <Card>{flags.map((f) => <FlagRow key={f.id} f={f} reload={state.reload} />)}</Card>}
      </Async>
    </>
  );
}

function FlagRow({ f, reload }) {
  const { run } = useToast();
  const [note, setNote] = useState("");
  const act = async (action) => {
    await run(() => api("PATCH", `/risk-flags/${f.id}`, { action, note }), "Đã cập nhật cảnh báo");
    reload();
  };
  return (
    <div className="list-item">
      <div className="row spread">
        <div className="row">
          <Badge status={f.severity} map={SEVERITY} />
          <Link to={`/internship/${f.internship_id}`}><b>{f.student.full_name}</b></Link>
          <Badge status={f.status} />
        </div>
        <span className="small muted">{fmtDate(f.created_at)}</span>
      </div>
      <p style={{ margin: "8px 0 12px" }}>{f.reason}</p>
      <div className="row">
        <input className="input" style={{ flex: 1, minWidth: 200 }} placeholder="Ghi chú (bắt buộc khi bác bỏ)" aria-label="Ghi chú"
          value={note} onChange={(e) => setNote(e.target.value)} />
        {f.status === "open" && <Button size="sm" onClick={() => act("acknowledge")}>Ghi nhận</Button>}
        <Button size="sm" variant="primary" onClick={() => act("resolve")}>Đã xử lý</Button>
        <Button size="sm" variant="danger" onClick={() => act("dismiss")}>Bác bỏ</Button>
      </div>
    </div>
  );
}
