import { useEffect } from "react";
import { Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { useToast } from "./context/ToastContext";
import AppShell from "./components/layout/AppShell";
import Login from "./features/auth/Login";
import StudentHome from "./features/student/StudentHome";
import StudentLogs from "./features/student/StudentLogs";
import LecturerQueue from "./features/lecturer/LecturerQueue";
import StudentList from "./features/lecturer/StudentList";
import InternshipDetail from "./features/lecturer/InternshipDetail";
import Flags from "./features/lecturer/Flags";
import AdminHome from "./features/admin/AdminHome";
import Assistant from "./features/shared/Assistant";
import Policies from "./features/shared/Policies";

// Bảng định tuyến theo vai trò. Thêm trang mới: thêm 1 <Route> + 1 dòng trong lib/config.js (NAV).

function SsoCallback() {
  const { token } = useParams();
  const { loginWithToken } = useAuth();
  const navigate = useNavigate();
  useEffect(() => { loginWithToken(token).finally(() => navigate("/", { replace: true })); }, [token]); // eslint-disable-line
  return <div className="splash">Đang đăng nhập…</div>;
}

function SsoError() {
  const { reason } = useParams();
  const { toast } = useToast();
  const navigate = useNavigate();
  useEffect(() => { toast("Đăng nhập SSO thất bại: " + decodeURIComponent(reason)); navigate("/", { replace: true }); }, []); // eslint-disable-line
  return null;
}

export default function App() {
  const { me, loading } = useAuth();

  return (
    <Routes>
      <Route path="/sso/:token" element={<SsoCallback />} />
      <Route path="/sso-error/:reason" element={<SsoError />} />
      {loading ? (
        <Route path="*" element={<div className="splash">Đang tải…</div>} />
      ) : !me ? (
        <Route path="*" element={<Login />} />
      ) : (
        <Route element={<AppShell />}>
          <Route path="assistant" element={<Assistant />} />
          <Route path="policies" element={<Policies />} />
          {me.role === "student" && (
            <>
              <Route index element={<StudentHome />} />
              <Route path="logs" element={<StudentLogs />} />
            </>
          )}
          {me.role === "lecturer" && (
            <>
              <Route index element={<LecturerQueue />} />
              <Route path="flags" element={<Flags />} />
            </>
          )}
          {me.role === "admin" && <Route index element={<AdminHome />} />}
          {me.role !== "student" && (
            <>
              <Route path="students" element={<StudentList />} />
              <Route path="internship/:id" element={<InternshipDetail />} />
            </>
          )}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      )}
    </Routes>
  );
}
