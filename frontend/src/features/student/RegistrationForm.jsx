import { useRef, useState } from "react";
import { useToast } from "../../context/ToastContext";
import { api, formData } from "../../lib/api";
import { FIELDS } from "../../lib/config";
import { AiBox, AiTag, Button, Card, CardHead, Citation, Field } from "../../components/ui";

// Form đăng ký thực tập (kèm điền tự động từ file giấy tiếp nhận bằng AI).

const MODES = [["full_time", "Toàn thời gian"], ["part_time", "Bán thời gian"]];

function initialValues(i) {
  return Object.fromEntries(FIELDS.map(([n]) => [n, i[n] || (n === "mode" ? "full_time" : "")]));
}

export default function RegistrationForm({ internship: i, editable, status, reload }) {
  const { toast, run } = useToast();
  const [values, setValues] = useState(() => initialValues(i));
  const [aiFields, setAiFields] = useState(() => new Set(i.ai_fields || []));
  const [version, setVersion] = useState(i.version);
  const [checks, setChecks] = useState(null); // null | { fails: [], ok: bool }
  const [intake, setIntake] = useState(null); // null | "loading" | {error} | result
  const fileRef = useRef();

  const change = (name, value) => {
    setValues((v) => ({ ...v, [name]: value }));
    setAiFields((s) => { const n = new Set(s); n.delete(name); return n; });
  };

  const save = async () => {
    const body = { version, ai_fields: [...aiFields] };
    FIELDS.forEach(([n]) => { body[n] = values[n].trim() || null; });
    const r = await api("PATCH", `/internships/${i.id}`, body);
    setVersion(r.version);
  };

  const showChecks = (results) => {
    const fails = results.filter((r) => r.passed === false || r.passed === undefined);
    setChecks({ fails, ok: fails.length === 0 });
  };

  const onCheck = async () => {
    await run(save);
    showChecks((await api("POST", `/internships/${i.id}/validate`)).results);
  };

  const onSubmit = async () => {
    await run(save);
    try {
      await api("POST", `/internships/${i.id}/submit`);
      toast("Đã nộp hồ sơ — chờ giảng viên duyệt");
      reload();
    } catch (e) {
      if (e.detail?.errors) showChecks(e.detail.errors); else toast(e.message);
    }
  };

  const onIntakeFile = async (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    setIntake("loading");
    try {
      setIntake(await api("POST", "/intake/extract", formData({ file }), true));
    } catch (e) {
      setIntake({ error: e.message });
    }
  };

  const applyIntake = () => {
    const next = { ...values };
    const ai = new Set(aiFields);
    Object.entries(intake.fields).forEach(([k, v]) => {
      if (v.needs_manual || !(k in next)) return;
      next[k] = v.value;
      ai.add(k);
    });
    setValues(next);
    setAiFields(ai);
    toast("Đã điền gợi ý — kiểm tra các ô tô màu xanh ngọc trước khi nộp");
  };

  const fieldProps = (name) => ({ id: `f-${name}`, value: values[name], disabled: !editable, ai: aiFields.has(name), onChange: (e) => change(name, e.target.value) });
  const label = (name) => FIELDS.find((f) => f[0] === name)[1];
  const hasError = (name) => checks?.fails.some((f) => (f.message || "").toLowerCase().includes(label(name).toLowerCase()));

  return (
    <Card>
      <CardHead title="Thông tin đăng ký">
        <div className="row">
          {status}
          {editable && (
            <>
              <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" onChange={onIntakeFile} hidden />
              <Button size="sm" onClick={() => fileRef.current.click()}>✦ Điền từ file giấy tiếp nhận</Button>
            </>
          )}
        </div>
      </CardHead>

      {intake === "loading" && <p className="muted">Đang đọc file…</p>}
      {intake?.error && <p className="errors">{intake.error}</p>}
      {intake?.fields && (
        <AiBox label={`${intake.label} · nguồn: ${intake.source === "llm" ? "mô hình AI" : "bộ trích xuất theo luật"}${intake.matched_company ? ` · khớp DN đã có: ${intake.matched_company.name}` : ""}`}>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Trường</th><th>Giá trị gợi ý</th><th>Độ tin cậy</th></tr></thead>
              <tbody>
                {Object.entries(intake.fields).map(([k, v]) => (
                  <tr key={k}>
                    <td>{(FIELDS.find((f) => f[0] === k) || [k, k])[1]}</td>
                    <td>{v.needs_manual ? <span className="muted">cần nhập tay</span> : v.value}</td>
                    <td>{Math.round(v.confidence * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Button variant="primary" size="sm" onClick={applyIntake} style={{ marginTop: 12 }}>Điền vào form</Button>
        </AiBox>
      )}

      <div className="grid2">
        {FIELDS.filter((f) => f[0] !== "job_description").map(([n, l, type]) =>
          type === "mode" ? (
            <Field key={n} as="select" label={l} {...fieldProps(n)}>
              {MODES.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </Field>
          ) : (
            <Field key={n} label={l} type={type === "date" ? "date" : "text"} error={hasError(n)} {...fieldProps(n)} />
          ),
        )}
      </div>
      <div style={{ marginTop: 16 }}>
        <Field as="textarea" label="Mô tả công việc" {...fieldProps("job_description")} />
      </div>

      {checks && (checks.ok
        ? <p className="badge ok" style={{ marginTop: 16 }}>Hồ sơ đạt mọi kiểm tra của quy chế</p>
        : <ul className="errors">{checks.fails.map((r, idx) => <li key={idx}>{r.message} <Citation c={r.citation} /></li>)}</ul>)}

      {editable && (
        <div className="form-actions">
          <Button variant="primary" onClick={onSubmit}>Xác nhận & nộp hồ sơ</Button>
          <Button onClick={() => run(save, "Đã lưu nháp")}>Lưu nháp</Button>
          <Button onClick={onCheck}>Kiểm tra theo quy chế</Button>
        </div>
      )}
      {aiFields.size > 0 && <p className="hint" style={{ marginTop: 12 }}><AiTag>AI</AiTag> Các ô tô màu xanh ngọc do AI gợi ý — hãy kiểm tra trước khi nộp.</p>}
    </Card>
  );
}
