// Hằng số: URL API, nhãn trạng thái, danh sách trường hồ sơ, menu theo vai trò.

export const API = "/api/v1";
export const STATUS = {
  draft: ["Nháp", ""], submitted: ["Chờ duyệt", "info"], revision_requested: ["Cần chỉnh sửa", "warn"],
  approved: ["Đã duyệt", "ok"], rejected: ["Từ chối", "bad"], in_progress: ["Đang thực tập", "info"],
  completed: ["Hoàn thành", "ok"], pending: ["Chưa nộp", ""], overdue: ["Quá hạn", "bad"],
  accepted: ["Đã chấp nhận", "ok"], returned: ["Trả lại", "warn"], open: ["Chờ duyệt", "info"],
  cancelled: ["Đã hủy", ""], acknowledged: ["Đã ghi nhận", "info"], resolved: ["Đã xử lý", "ok"],
  dismissed: ["Bác bỏ", ""], active: ["Đang hiệu lực", "ok"], superseded: ["Đã bị thay thế", "warn"],
};
export const SEVERITY = { info: ["Thông tin", "info"], warning: ["Cảnh báo", "warn"], critical: ["Nghiêm trọng", "bad"] };
export const FIELDS = [
  ["company_name", "Tên doanh nghiệp"], ["company_tax_code", "Mã số thuế"], ["company_address", "Địa chỉ doanh nghiệp"],
  ["position", "Vị trí thực tập"], ["mentor_name", "Người hướng dẫn tại DN"], ["mentor_email", "Email người hướng dẫn"],
  ["mentor_phone", "SĐT người hướng dẫn"], ["start_date", "Ngày bắt đầu", "date"], ["end_date", "Ngày kết thúc", "date"],
  ["mode", "Hình thức", "mode"], ["job_description", "Mô tả công việc", "textarea"],
];
export const NAV = {
  student: [["#/", "Hồ sơ của tôi"], ["#/logs", "Nhật ký"], ["#/assistant", "Trợ lý AI"], ["#/policies", "Quy định"]],
  lecturer: [["#/", "Hàng chờ duyệt"], ["#/students", "Sinh viên"], ["#/flags", "Cảnh báo"], ["#/assistant", "Trợ lý AI"], ["#/policies", "Quy định"]],
  admin: [["#/", "Quản trị"], ["#/students", "Danh sách"], ["#/policies", "Quy định"], ["#/assistant", "Trợ lý AI"]],
};
