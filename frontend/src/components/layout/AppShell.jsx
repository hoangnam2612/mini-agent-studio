import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { ChatProvider } from "../../context/ChatContext";
import { NAV, ROLE_LABEL } from "../../lib/config";
import { Avatar } from "../ui";
import ThemeToggle from "../ui/ThemeToggle";
import Icon from "../ui/Icon";
import Notifications from "./Notifications";

// Khung chung: sidebar điều hướng theo vai trò + chuông thông báo + vùng nội dung.

export default function AppShell() {
  const { me, logout } = useAuth();
  const [bellOpen, setBellOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setBellOpen(false), [location]);

  return (
    <ChatProvider>
      <div className="shell">
        <aside className="sidebar">
          <Link to="/" className="brand">
            <span className="brand__mark"><Icon name="cap" /></span>
            Cổng thực tập
          </Link>
          <nav className="nav" aria-label="Điều hướng chính">
            {NAV[me.role].map(([to, label, icon, end]) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav__link ${isActive ? "active" : ""}`}>
                <Icon name={icon} />{label}
              </NavLink>
            ))}
          </nav>
          <ThemeToggle className="theme-toggle--side" />
          <div className="userbox">
            <Avatar name={me.full_name} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="userbox__name">{me.full_name}</div>
              <div className="userbox__role">{ROLE_LABEL[me.role]}</div>
            </div>
            <button className="icon-btn icon-btn--plain" onClick={logout} aria-label="Đăng xuất"><Icon name="logout" /></button>
          </div>
        </aside>
        <main className="content" aria-live="polite">
          <div className="content__inner">
            <div className="row" style={{ justifyContent: "flex-end", marginBottom: -8 }}>
              <Notifications open={bellOpen} setOpen={setBellOpen} />
            </div>
            <Outlet />
          </div>
        </main>
      </div>
    </ChatProvider>
  );
}
