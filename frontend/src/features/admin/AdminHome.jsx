import { useState } from "react";
import { useToast } from "../../context/ToastContext";
import { useAsync } from "../../hooks/useAsync";
import { api } from "../../lib/api";
import { Async, Button, Card, CardHead, Field, PageHead } from "../../components/ui";

// Trang quản trị: mẫu mốc, phân công GV, tạo tài khoản.

export default function AdminHome() {
  const state = useAsync(async () => {
    const [users, cohort] = await Promise.all([api("GET", "/admin/users"), api("GET", "/admin/cohort")]);
    return { users, cohort };
  });
  const { toast, run } = useToast();

  const runMonitor = async () => {
    const r = await run(() => api("POST", "/monitor/run"));
    toast(`Giám sát xong: ${r.flags_created} cảnh báo mới, ${r.overdue} mốc quá hạn`);
  };

  return (
    <Async state={state}>
      {({ users, cohort }) => (
        <>
          <PageHead title="Quản trị" subtitle={`Đợt: ${cohort.name} (${cohort.code})`}>
            <Button onClick={runMonitor}>Chạy giám sát ngay</Button>
          </PageHead>
          <TemplateEditor key={JSON.stringify(cohort.templates)} templates={cohort.templates} reload={state.reload} />
          <Assignments users={users} />
          <UserForm reload={state.reload} />
        </>
      )}
    </Async>
  );
}

const ANCHORS = { start: "Ngày bắt đầu", mid: "Giữa kỳ", end: "Ngày kết thúc" };

const toRow = (t) => ({
  code: t.code, name: t.name, anchor: t.anchor, offset_days: t.offset_days,
  required_evidence: (t.required_evidence || []).join(", "), linked_to: t.linked_to || null,
  citation: t.citation?.doc ? `${t.citation.doc} · ${t.citation.path}` : "",
});

function TemplateEditor({ templates, reload }) {
  const { run } = useToast();
  const [rows, setRows] = useState(() => templates.map(toRow));
  const edit = (idx, key, value) => setRows((r) => r.map((row, i) => (i === idx ? { ...row, [key]: value } : row)));

  const save = async () => {
    const body = rows.map((r) => {
      const [doc, ...path] = r.citation.split("·").map((s) => s.trim());
      return {
        code: r.code.trim(), name: r.name.trim(), anchor: r.anchor, offset_days: Number(r.offset_days),
        required_evidence: r.required_evidence.trim() ? r.required_evidence.split(",").map((s) => s.trim()).filter(Boolean) : [],
        linked_to: r.linked_to, citation: doc ? { doc, path: path.join(" · ") } : {},
      };
    });
    await run(() => api("PUT", "/admin/cohort/templates", body), "Đã lưu mẫu mốc");
    reload();
  };

  const cell = { minHeight: 40, padding: "6px 10px" };
  return (
    <Card>
      <CardHead title="Mẫu mốc của đợt" />
      <p className="small muted">Thay đổi chỉ áp dụng cho hồ sơ được duyệt sau thời điểm lưu; mốc đã sinh giữ nguyên.</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Mã</th><th>Tên mốc</th><th>Mốc tính hạn</th><th>Lệch (ngày)</th><th>Minh chứng yêu cầu</th><th>Căn cứ</th><th /></tr></thead>
          <tbody>
            {rows.map((r, idx) => (
              <tr key={idx}>
                <td><input className="input" style={{ ...cell, minWidth: 90 }} aria-label="Mã" value={r.code} onChange={(e) => edit(idx, "code", e.target.value)} /></td>
                <td><input className="input" style={{ ...cell, minWidth: 200 }} aria-label="Tên mốc" value={r.name} onChange={(e) => edit(idx, "name", e.target.value)} /></td>
                <td>
                  <select className="input" style={cell} aria-label="Mốc tính hạn" value={r.anchor} onChange={(e) => edit(idx, "anchor", e.target.value)}>
                    {Object.entries(ANCHORS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                  </select>
                </td>
                <td><input className="input" style={{ ...cell, width: 90 }} type="number" aria-label="Lệch ngày" value={r.offset_days} onChange={(e) => edit(idx, "offset_days", e.target.value)} /></td>
                <td><input className="input" style={cell} aria-label="Minh chứng yêu cầu" value={r.required_evidence} disabled={Boolean(r.linked_to)}
                  placeholder={r.linked_to ? "theo đề cương" : "vd final_report"} onChange={(e) => edit(idx, "required_evidence", e.target.value)} /></td>
                <td><input className="input" style={{ ...cell, minWidth: 200 }} aria-label="Căn cứ" value={r.citation} placeholder="QĐ-TT/2026 · Điều 7 / Khoản 1" onChange={(e) => edit(idx, "citation", e.target.value)} /></td>
                <td><Button size="sm" variant="danger" aria-label="Xóa mốc" onClick={() => setRows((l) => l.filter((_, i) => i !== idx))}>✕</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="form-actions">
        <Button onClick={() => setRows((r) => [...r, { code: "", name: "", anchor: "start", offset_days: 7, required_evidence: "", linked_to: null, citation: "" }])}>Thêm mốc</Button>
        <Button variant="primary" onClick={save}>Lưu mẫu mốc</Button>
      </div>
    </Card>
  );
}

function Assignments({ users }) {
  const { run } = useToast();
  const lecturers = users.filter((u) => u.role === "lecturer");
  const assign = (studentId, lecturerId) =>
    run(() => api("POST", "/admin/assign", { student_id: studentId, lecturer_id: Number(lecturerId) }), "Đã phân công");
  return (
    <Card>
      <CardHead title="Phân công giảng viên" />
      <div className="table-wrap">
        <table>
          <thead><tr><th>Sinh viên</th><th>Mã SV</th><th>GV phụ trách</th></tr></thead>
          <tbody>
            {users.filter((u) => u.role === "student").map((s) => (
              <tr key={s.id}>
                <td>{s.full_name}</td><td>{s.student_code}</td>
                <td>
                  <select className="input" style={{ minHeight: 40, padding: "6px 10px" }} aria-label={`GV phụ trách ${s.full_name}`} defaultValue={s.lecturer_id} onChange={(e) => assign(s.id, e.target.value)}>
                    {lecturers.map((l) => <option key={l.id} value={l.id}>{l.full_name}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function UserForm({ reload }) {
  const { run } = useToast();
  const submit = async (ev) => {
    ev.preventDefault();
    const body = Object.fromEntries(new FormData(ev.target));
    if (!body.student_code) delete body.student_code;
    await run(() => api("POST", "/admin/users", body), "Đã tạo tài khoản");
    ev.target.reset();
    reload();
  };
  return (
    <Card>
      <CardHead title="Thêm tài khoản" />
      <form onSubmit={submit}>
        <div className="grid2">
          <Field id="u-name" name="username" label="Tên đăng nhập" required pattern="[a-z0-9_.]+" />
          <Field id="u-pw" name="password" type="password" label="Mật khẩu" minLength={6} required />
          <Field id="u-full" name="full_name" label="Họ tên" required />
          <Field id="u-role" as="select" name="role" label="Vai trò" defaultValue="student">
            <option value="student">Sinh viên</option><option value="lecturer">Giảng viên</option>
          </Field>
          <Field id="u-mail" name="email" label="Email" />
          <Field id="u-code" name="student_code" label="Mã SV" />
        </div>
        <div className="form-actions"><button className="btn btn--primary" type="submit">Tạo tài khoản</button></div>
      </form>
    </Card>
  );
}
