import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { api } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import { Badge, Button, Card, CardHead } from "../../components/ui";

// Danh sách yêu cầu gia hạn của sinh viên (hủy được khi còn đang chờ).

export default function ExtensionList({ extensions, reload }) {
  const { me } = useAuth();
  const { run } = useToast();
  const cancel = async (id) => { await run(() => api("POST", `/extensions/${id}/cancel`), "Đã hủy yêu cầu"); reload(); };

  return (
    <Card>
      <CardHead title="Yêu cầu gia hạn" />
      {extensions.map((e) => (
        <div key={e.id} className="list-item row spread">
          <div>
            <b>{e.milestone.name}</b> <Badge status={e.status} />
            <div className="small muted">{fmtDate(e.previous_due_date)} → {fmtDate(e.requested_due_date)} · {e.reason}</div>
            {e.decision_reason && <div className="small">GV: {e.decision_reason}</div>}
          </div>
          {e.status === "open" && me.role === "student" && <Button size="sm" variant="danger" onClick={() => cancel(e.id)}>Hủy</Button>}
        </div>
      ))}
    </Card>
  );
}
