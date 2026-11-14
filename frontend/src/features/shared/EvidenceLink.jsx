import { useToast } from "../../context/ToastContext";
import { api } from "../../lib/api";

// Nút mở file minh chứng (lấy URL tạm từ API rồi mở tab mới).

export function EvidenceLink({ id, children }) {
  const { run } = useToast();
  const open = async () => {
    const { url } = await run(() => api("GET", `/evidence/${id}/url`));
    window.open(url, "_blank", "noopener");
  };
  return <button type="button" className="link-btn" style={{ marginRight: 12 }} onClick={open}>{children}</button>;
}
