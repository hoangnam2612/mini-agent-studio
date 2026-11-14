import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { useToast } from "../../context/ToastContext";
import { API } from "../../lib/config";
import { api } from "../../lib/api";
import { Button, Field } from "../../components/ui";
import Icon from "../../components/ui/Icon";
import ThemeToggle from "../../components/ui/ThemeToggle";

const DEMO = [["sv03", "Sinh viên"], ["gv01", "Giảng viên"], ["admin", "Quản trị"]];

export default function Login() {
  const { login } = useAuth();
  const { run } = useToast();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [sso, setSso] = useState(false);

  useEffect(() => {
    api("GET", "/auth/oidc/config").then((c) => setSso(Boolean(c.enabled))).catch(() => {});
  }, []);

  const submit = async (ev) => {
    ev.preventDefault();
    setBusy(true);
    try { await run(() => login(username, password)); } catch (_) { /* đã báo lỗi bằng toast */ } finally { setBusy(false); }
  };

  return (
    <div className="login">
      <section className="login__hero">
        <div className="brand"><span className="brand__mark"><Icon name="cap" /></span>Cổng thực tập</div>
        <div>
          <h1>Mỗi chặng thực tập, một bước rõ ràng.</h1>
          <p>Nộp hồ sơ, theo dõi các mốc, ghi nhật ký tuần và hỏi trợ lý về quy định — tất cả ở một nơi.</p>
          <svg className="login__route" viewBox="0 0 460 90" fill="none" aria-hidden="true">
            <path d="M12 60 H120 Q150 60 150 30 Q150 14 180 14 H300 Q330 14 330 44 Q330 72 360 72 H448" stroke="#dce6f8" strokeWidth="4" strokeDasharray="2 10" strokeLinecap="round" />
            {[[12, 60], [150, 30], [330, 44]].map(([x, y]) => <rect key={x} x={x - 12} y={y - 12} width="24" height="24" rx="6" fill="#fff" />)}
            <rect x="436" y="60" width="24" height="24" rx="6" fill="#9db9ee" />
          </svg>
        </div>
        <div className="login__foot">Hệ thống hỗ trợ thực tập bằng AI · VIN-15</div>
      </section>

      <section className="login__panel">
        <div className="login__form">
          <ThemeToggle className="theme-toggle--login" />
          <h2 style={{ fontSize: "1.75rem", marginBottom: 8 }}>Chào mừng quay lại</h2>
          <p className="muted" style={{ marginBottom: 28 }}>Đăng nhập để tiếp tục.</p>
          <form className="field-stack" onSubmit={submit}>
            <Field id="u" label="Tên đăng nhập" value={username} onChange={(e) => setUsername(e.target.value)}
              autoComplete="username" placeholder="ví dụ: sv03" required />
            <Field id="p" label="Mật khẩu" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password" placeholder="••••••••" required />
            <button className="btn btn--primary btn--block" type="submit" disabled={busy}>{busy ? "Đang đăng nhập…" : "Đăng nhập"}</button>
            {sso && <a className="btn btn--block" href={`${API}/auth/oidc/login`}>Đăng nhập bằng tài khoản trường (SSO)</a>}
          </form>
          <div className="demo">
            <div className="demo__title">Tài khoản demo · mật khẩu demo123 (bấm để điền)</div>
            <div className="chips">
              {DEMO.map(([u, label]) => (
                <button key={u} type="button" className="chip" onClick={() => { setUsername(u); setPassword("demo123"); }}>{u} · {label}</button>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
