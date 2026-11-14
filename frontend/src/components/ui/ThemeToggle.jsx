import { useTheme } from "../../hooks/useTheme";
import Icon from "./Icon";

// Chọn giao diện: Tự động / Sáng / Tối.
const OPTIONS = [["auto", "monitor", "Tự động theo thiết bị"], ["light", "sun", "Sáng"], ["dark", "moon", "Tối"]];

export default function ThemeToggle({ className = "" }) {
  const [mode, setMode] = useTheme();
  return (
    <div className={`theme-toggle ${className}`} role="radiogroup" aria-label="Giao diện">
      {OPTIONS.map(([value, icon, label]) => (
        <button key={value} type="button" role="radio" aria-checked={mode === value} aria-label={label} title={label}
          className={mode === value ? "is-on" : ""} onClick={() => setMode(value)}>
          <Icon name={icon} size={18} />
        </button>
      ))}
    </div>
  );
}
