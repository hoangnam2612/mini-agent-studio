import { state } from "./core/state.js";
import { $, esc } from "./core/utils.js";
import { renderLogin } from "./core/auth.js";
import { renderShell, refreshBell } from "./components/shell.js";
import { studentHome } from "./views/student/home.js";
import { studentLogs } from "./views/student/logs.js";
import { assistantView } from "./views/shared/assistant.js";
import { policiesView } from "./views/shared/policies.js";
import { lecturerQueue } from "./views/lecturer/queue.js";
import { lecturerStudents } from "./views/lecturer/students.js";
import { lecturerInternship } from "./views/lecturer/internship.js";
import { lecturerFlags } from "./views/lecturer/flags.js";
import { adminHome } from "./views/admin/home.js";

// Router theo hash.

export async function route() {
  if (!state.me) return renderLogin();
  renderShell();
  const parts = (location.hash || "#/").slice(2).split("/");
  const role = state.me.role;
  try {
    if (parts[0] === "assistant") return assistantView();
    if (parts[0] === "policies") return await policiesView();
    if (role === "student") return parts[0] === "logs" ? await studentLogs() : await studentHome();
    if (role === "lecturer") {
      if (parts[0] === "students") return await lecturerStudents();
      if (parts[0] === "internship" && parts[1]) return await lecturerInternship(parts[1]);
      if (parts[0] === "flags") return await lecturerFlags();
      return await lecturerQueue();
    }
    if (parts[0] === "students") return await lecturerStudents();
    if (parts[0] === "internship" && parts[1]) return await lecturerInternship(parts[1]);
    return await adminHome();
  } catch (e) {
    $("#app").innerHTML = `<div class="card errors">${esc(e.message)}</div>`;
  } finally {
    refreshBell();
  }
}
