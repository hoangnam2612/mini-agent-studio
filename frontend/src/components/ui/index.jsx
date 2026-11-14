import { STATUS } from "../../lib/config";
import Icon from "./Icon";

// Các thành phần UI nhỏ dùng khắp nơi. Style ở styles/components.css.

export function Badge({ status, map = STATUS, children }) {
  const [text, tone] = children ? [children, status] : map[status] || [status, ""];
  return <span className={`badge ${tone}`}>{text}</span>;
}

export const AiTag = ({ children = "AI điền" }) => <span className="badge ai">{children}</span>;

export function Button({ variant, size, block, className = "", ...props }) {
  const cls = ["btn", variant && `btn--${variant}`, size && `btn--${size}`, block && "btn--block", className].filter(Boolean).join(" ");
  return <button type="button" className={cls} {...props} />;
}

export const Card = ({ className = "", ...props }) => <section className={`card ${className}`} {...props} />;

export function CardHead({ title, children }) {
  return (
    <div className="card__head">
      <h2>{title}</h2>
      {children}
    </div>
  );
}

export function PageHead({ title, subtitle, children }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

/** Ô nhập có nhãn. `as`: input | select | textarea. */
export function Field({ label, id, as: Tag = "input", ai, error, hint, children, className = "", ...props }) {
  return (
    <div className={`field ${ai ? "is-ai" : ""} ${error ? "has-error" : ""} ${className}`}>
      <label htmlFor={id}>
        {label}
        {ai && <> <AiTag>AI điền · hãy kiểm tra</AiTag></>}
      </label>
      <Tag id={id} {...props}>{children}</Tag>
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

export function Alert({ tone = "warn", title, children }) {
  return (
    <div className={`alert alert--${tone}`} role="alert">
      <Icon name="alert" />
      <div>
        {title && <div className="alert__title">{title}</div>}
        <div>{children}</div>
      </div>
    </div>
  );
}

export function AiBox({ label, children }) {
  return (
    <div className="ai-box">
      <div className="ai-label"><Icon name="sparkle" size={16} />{label}</div>
      {children}
    </div>
  );
}

export const Empty = ({ children }) => <div className="card card--empty">{children}</div>;
export const Loading = () => <div className="card card--empty">Đang tải…</div>;
export const ErrorBox = ({ error }) => <div className="card"><p className="errors" style={{ margin: 0, listStyle: "none", padding: 0 }}>{error.message}</p></div>;

/** Bao trạng thái tải/lỗi của useAsync. */
export function Async({ state, children }) {
  if (state.loading && !state.data) return <Loading />;
  if (state.error && !state.data) return <ErrorBox error={state.error} />;
  return children(state.data);
}

export const Avatar = ({ name }) => (
  <div className="avatar" aria-hidden="true">{name.trim().split(/\s+/).slice(-2).map((w) => w[0]).join("").toUpperCase()}</div>
);

export const Citation = ({ c }) =>
  c?.doc ? <span className="small muted">Căn cứ: {c.doc} · {c.path}</span> : null;
