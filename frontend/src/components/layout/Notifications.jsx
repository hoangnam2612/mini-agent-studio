import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { fmtDate } from "../../lib/format";
import Icon from "../ui/Icon";

// Chuông thông báo + bảng danh sách. Tự tải lại khi đổi trang (nhận `key` từ cha qua location).

export default function Notifications({ open, setOpen }) {
  const [list, setList] = useState([]);

  const refresh = useCallback(async () => {
    try { setList(await api("GET", "/notifications")); } catch (_) { /* không chặn trang */ }
  }, []);

  useEffect(() => { refresh(); }, [refresh, open]);

  const unread = list.filter((n) => !n.read).length;

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && unread) {
      await api("POST", "/notifications/read-all").catch(() => {});
      // giữ dấu "chưa đọc" trong lúc panel đang mở, chỉ xóa số đếm
      setList((l) => l.map((n) => ({ ...n, read: true, wasUnread: !n.read })));
    }
  };

  return (
    <>
      <button className="icon-btn" onClick={toggle} aria-label="Thông báo" aria-expanded={open}>
        <Icon name="bell" size={22} />
        {unread > 0 && <span className="icon-btn__count">{unread}</span>}
      </button>
      {open && (
        <div className="notif-panel" role="dialog" aria-label="Thông báo">
          {list.length === 0 && <p className="muted" style={{ padding: 12, margin: 0 }}>Chưa có thông báo.</p>}
          {list.map((n) => (
            <Link key={n.id} to={(n.link || "#/").replace(/^#/, "") || "/"} className={`notif-panel__item ${n.wasUnread ? "unread" : ""}`}>
              <div style={{ fontWeight: n.wasUnread ? 600 : 500 }}>{n.title}</div>
              {n.body && <div className="muted small">{n.body}</div>}
              <div className="muted small">{fmtDate(n.created_at)}</div>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
