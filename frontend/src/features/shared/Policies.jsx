import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useAsync } from "../../hooks/useAsync";
import { api } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import { Async, Badge, Card, CardHead, Field, PageHead } from "../../components/ui";

// Văn bản quy định (dùng chung mọi vai trò); người có quyền có thể tải văn bản mới.

export default function Policies() {
  const { me } = useAuth();
  const state = useAsync(() => api("GET", "/policies"));
  return (
    <>
      <PageHead title="Văn bản quy định" subtitle="Nguồn duy nhất để trợ lý AI trả lời và dẫn căn cứ." />
      <Async state={state}>
        {(docs) => (
          <>
            <PolicyTable docs={docs} />
            {me.can_manage_policies && <UploadForm reload={state.reload} />}
          </>
        )}
      </Async>
    </>
  );
}

function PolicyTable({ docs }) {
  const [open, setOpen] = useState(null);
  const view = async (id) => setOpen(await api("GET", `/policies/${id}`));
  return (
    <Card>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Số hiệu</th><th>Tên văn bản</th><th>Hiệu lực</th><th>Trạng thái</th><th>Số đoạn</th></tr></thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id}>
                <td><button className="link-btn" onClick={() => view(d.id)}>{d.code}</button></td>
                <td>{d.title}<div className="small muted">{d.issuer}</div></td>
                <td>{fmtDate(d.effective_from)}{d.effective_to ? ` – ${fmtDate(d.effective_to)}` : ""}</td>
                <td><Badge status={d.status} /></td>
                <td>{d.chunk_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {open && (
        <div style={{ marginTop: 20 }}>
          <h3>{open.code} — {open.title}</h3>
          {open.chunks.map((c) => <details key={c.path}><summary>{c.path}</summary><p className="pre">{c.text}</p></details>)}
        </div>
      )}
    </Card>
  );
}

function UploadForm({ reload }) {
  const { run } = useToast();
  const submit = async (ev) => {
    ev.preventDefault();
    const fd = new FormData(ev.target);
    if (!fd.get("supersedes_code")) fd.delete("supersedes_code");
    await run(() => api("POST", "/policies", fd, true), "Đã tải và lập chỉ mục văn bản");
    ev.target.reset();
    reload();
  };
  return (
    <Card>
      <CardHead title="Tải văn bản mới" />
      <form onSubmit={submit}>
        <div className="grid2">
          <Field id="p-code" name="code" label="Số hiệu" required />
          <Field id="p-title" name="title" label="Tên văn bản" required />
          <Field id="p-from" name="effective_from" type="date" label="Hiệu lực từ" required />
          <Field id="p-sup" name="supersedes_code" label="Thay thế văn bản (số hiệu, nếu có)" />
          <Field id="p-iss" name="issuer" label="Cơ quan ban hành" />
          <Field id="p-file" name="file" type="file" label={'File (PDF/DOCX/MD/TXT, có dòng "Điều N.")'} accept=".pdf,.docx,.md,.txt" required />
        </div>
        <div className="form-actions"><button className="btn btn--primary" type="submit">Tải lên & lập chỉ mục</button></div>
      </form>
    </Card>
  );
}
