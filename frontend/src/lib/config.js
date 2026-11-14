// Hằng số: URL API, nhãn trạng thái, danh sách trường hồ sơ, menu theo vai trò.

export const API = "/api/v1";

// [nhãn, tông màu] — tông: ok | warn | bad | info | "" (trung tính)
export const STATUS = {
  draft: ["Nháp", ""], submitted: ["Chờ duyệt", "info"], revision_requested: ["Cần chỉnh sửa", "warn"],
  approved: ["Đã duyệt", "ok"], rejected: ["Từ chối", "bad"], in_progress: ["Đang thực tập", "info"],
  completed: ["Hoàn thành", "ok"], pending: ["Chưa nộp", ""], overdue: ["Quá hạn", "bad"],
  accepted: ["Đã chấp nhận", "ok"], returned: ["Trả lại", "warn"], open: ["Chờ duyệt", "info"],
  cancelled: ["Đã hủy", ""], acknowledged: ["Đã ghi nhận", "info"], resolved: ["Đã xử lý", "ok"],
  dismissed: ["Bác bỏ", ""], active: ["Đang hiệu lực", "ok"], superseded: ["Đã bị thay thế", "warn"],
};
export const SEVERITY = { info: ["Thông tin", "info"], warning: ["Cảnh báo", "warn"], critical: ["Nghiêm trọng", "bad"] };

// [tên trường, nhãn, kiểu]
export const FIELDS = [
  ["company_name", "Tên doanh nghiệp"], ["company_tax_code", "Mã số thuế"], ["company_address", "Địa chỉ doanh nghiệp"],
  ["position", "Vị trí thực tập"], ["mentor_name", "Người hướng dẫn tại DN"], ["mentor_email", "Email người hướng dẫn"],
  ["mentor_phone", "SĐT người hướng dẫn"], ["start_date", "Ngày bắt đầu", "date"], ["end_date", "Ngày kết thúc", "date"],
  ["mode", "Hình thức", "mode"], ["job_description", "Mô tả công việc", "textarea"],
];

export const ROLE_LABEL = { student: "Sinh viên", lecturer: "Giảng viên", admin: "Quản trị viên" };

// [đường dẫn, nhãn, icon, exact]
export const NAV = {
  student: [["/", "Hồ sơ của tôi", "file", true], ["/logs", "Nhật ký", "notebook"], ["/assistant", "Trợ lý AI", "chat"], ["/policies", "Quy định", "book"]],
  lecturer: [["/", "Hàng chờ duyệt", "inbox", true], ["/students", "Sinh viên", "users"], ["/flags", "Cảnh báo", "flag"], ["/assistant", "Trợ lý AI", "chat"], ["/policies", "Quy định", "book"]],
  admin: [["/", "Quản trị", "settings", true], ["/students", "Danh sách", "users"], ["/policies", "Quy định", "book"], ["/assistant", "Trợ lý AI", "chat"]],
};

export const TOKEN_KEY = "vin15_token";
