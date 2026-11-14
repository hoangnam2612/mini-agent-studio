import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { useAsync } from "../../hooks/useAsync";
import { api, downloadFile } from "../../lib/api";
import { SEVERITY, STATUS } from "../../lib/config";
import { fmtDate } from "../../lib/format";
import { Async, Badge, Button, Card, Field, PageHead } from "../../components/ui";

// Danh sách sinh viên: lọc, sắp xếp, phân trang, xuất file.

const STATUS_FILTERS = ["draft", "submitted", "revision_requested", "approved", "rejected", "in_progress", "completed"];
const RISKS = [["", "Tất cả"], ["any", "Có cảnh báo"], ["none", "Không cảnh báo"], ["critical", "Nghiêm trọng"], ["warning", "Cảnh báo"], ["info", "Thông tin"]];
const BASE_PROGRAMS = ["Công nghệ thông tin", "Quản trị kinh doanh"];

const toQuery = (filters, extra = {}) => {
  const p = new URLSearchParams();
  Object.entries({ ...filters, ...extra }).forEach(([k, v]) => { if (v !== "" && v != null) p.set(k, v); });
  return p.toString();
};

export default function StudentList() {
  const { me } = useAuth();
  const { toast } = useToast();
  const isAdmin = me.role === "admin";
  const [filters, setFilters] = useState({ q: "", status: "", program: "", risk: "", lecturer_id: "", sort: "risk", order: "desc", page: 1 });
  const [search, setSearch] = useState("");

  const state = useAsync(async () => {
    const [data, users] = await Promise.all([
      api("GET", `/internships-summary?${toQuery(filters, { page_size: 25 })}`),
      isAdmin ? api("GET", "/admin/users") : Promise.resolve([]),
    ]);
    return { data, users };
  }, [filters]);

  const apply = (changes) => setFilters((f) => ({ ...f, ...changes }));
  const sortBy = (key) => apply({ sort: key, order: filters.sort === key && filters.order === "desc" ? "asc" : "desc", page: 1 });
  const exportAs = (format) => downloadFile(`/internships-summary/export?${toQuery(filters, { format, page: undefined })}`, `danh-sach.${format}`).catch((e) => toast(e.message));

  return (
    <>
      <PageHead title={isAdmin ? "Danh sách thực tập toàn khóa" : "Sinh viên phụ trách"}>
        <div className="row">
          <Button size="sm" onClick={() => exportAs("csv")}>Xuất CSV</Button>
          <Button size="sm" onClick={() => exportAs("xlsx")}>Xuất Excel</Button>
        </div>
      </PageHead>
      <Card>
        <form className="grid2 filters" onSubmit={(e) => { e.preventDefault(); apply({ q: search.trim(), page: 1 }); }}>
          <Field id="sf-q" label="Tìm (tên, mã SV, doanh nghiệp)" value={search} onChange={(e) => setSearch(e.target.value)} onBlur={() => apply({ q: search.trim(), page: 1 })} />
          <Field id="sf-status" as="select" label="Trạng thái" value={filters.status} onChange={(e) => apply({ status: e.target.value, page: 1 })}>
            <option value="">Tất cả</option>
            {STATUS_FILTERS.map((s) => <option key={s} value={s}>{STATUS[s][0]}</option>)}
          </Field>
          <Async state={state}>
            {({ data, users }) => (
              <>
                <Field id="sf-program" as="select" label="Ngành" value={filters.program} onChange={(e) => apply({ program: e.target.value, page: 1 })}>
                  <option value="">Tất cả</option>
                  {[...new Set([...BASE_PROGRAMS, ...data.facets.programs])].map((p) => <option key={p}>{p}</option>)}
                </Field>
                <Field id="sf-risk" as="select" label="Mức rủi ro" value={filters.risk} onChange={(e) => apply({ risk: e.target.value, page: 1 })}>
                  {RISKS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </Field>
                {isAdmin && (
                  <Field id="sf-lecturer" as="select" label="Giảng viên" value={filters.lecturer_id} onChange={(e) => apply({ lecturer_id: e.target.value, page: 1 })}>
                    <option value="">Tất cả</option>
                    {users.filter((u) => u.role === "lecturer").map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
                  </Field>
                )}
              </>
            )}
          </Async>
        </form>

        <Async state={state}>
          {({ data }) => {
            const pages = Math.max(1, Math.ceil(data.total / data.page_size));
            const Th = ({ k, children }) => (
              <th><button className="th-sort" onClick={() => sortBy(k)}>{children}{filters.sort === k ? (filters.order === "asc" ? " ▲" : " ▼") : ""}</button></th>
            );
            return (
              <>
                <p className="small muted">{data.total} hồ sơ · trang {data.page}/{pages}</p>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><Th k="student">Sinh viên</Th><Th k="company">Doanh nghiệp</Th><Th k="status">Trạng thái</Th><Th k="progress">% mốc</Th><Th k="next_due">Mốc kế tiếp</Th><Th k="risk">Cảnh báo</Th>{isAdmin && <th>GV</th>}</tr>
                    </thead>
                    <tbody>
                      {data.items.map((r) => (
                        <tr key={r.id}>
                          <td><Link to={`/internship/${r.id}`}><b>{r.student_name}</b></Link><div className="small muted">{r.student_code} · {r.program}</div></td>
                          <td>{r.company || "—"}</td>
                          <td><Badge status={r.status} /></td>
                          <td style={{ minWidth: 110 }}><div className="progress" role="progressbar" aria-valuenow={r.progress_pct} aria-valuemin="0" aria-valuemax="100"><span style={{ width: `${r.progress_pct}%` }} /></div><span className="small muted">{r.progress_pct}%</span></td>
                          <td className="small">{r.next_milestone ? <>{r.next_milestone}<div className="muted">{fmtDate(r.next_due)} {r.next_status === "overdue" && <Badge status="overdue" />}</div></> : "—"}</td>
                          <td>{r.open_flags ? <><Badge status={r.max_severity} map={SEVERITY} /> ×{r.open_flags}</> : <span className="muted">—</span>}</td>
                          {isAdmin && <td className="small">{r.lecturer}</td>}
                        </tr>
                      ))}
                      {data.items.length === 0 && <tr><td colSpan="7" className="muted">Không có hồ sơ phù hợp.</td></tr>}
                    </tbody>
                  </table>
                </div>
                <div className="pager">
                  <Button size="sm" disabled={data.page <= 1} onClick={() => apply({ page: filters.page - 1 })}>← Trước</Button>
                  <Button size="sm" disabled={data.page >= pages} onClick={() => apply({ page: filters.page + 1 })}>Sau →</Button>
                </div>
              </>
            );
          }}
        </Async>
      </Card>
    </>
  );
}
