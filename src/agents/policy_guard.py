"""Guardrail theo domain cho trợ lý chính sách (R8.6–8.7).

Bổ sung cho `guardrails.check_input` (pattern tiếng Anh của template):
- prompt injection tiếng Việt → từ chối
- hỏi dữ liệu SV khác (mã SV lạ, "hồ sơ của sinh viên khác") → từ chối
- yêu cầu ra quyết định ("duyệt cho em", "em được gia hạn không") → KHÔNG từ chối,
  đánh dấu decision_request để câu trả lời giải thích quy định + hướng dẫn tạo yêu cầu.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.agents.guardrails import GuardrailViolation, guardrails

_INJECTION_VI = (
    re.compile(r"bỏ\s+qua\s+(?:(?:tất\s+cả|mọi|các|những)\s+)*(?:hướng\s+dẫn|chỉ\s+dẫn|quy\s+tắc|lệnh|ràng\s+buộc)", re.I),
    re.compile(r"(?:tiết\s+lộ|in\s+ra|cho\s+(?:tôi\s+|em\s+)?xem)\s+(?:system\s+prompt|prompt\s+hệ\s+thống|lời\s+nhắc\s+hệ\s+thống)", re.I),
    re.compile(r"(?:giả\s+vờ|đóng\s+vai|coi\s+như)\s+(?:bạn\s+)?(?:là\s+)?(?:giảng\s+viên|quản\s+trị|admin)", re.I),
)
_STUDENT_CODE = re.compile(r"\b[Ss][Vv]\d{4,}\b|(?<!\d)\d{8}(?!\d)")
_OTHER_STUDENT = (
    re.compile(r"(?:hồ\s+sơ|điểm|thông\s+tin|nhật\s+ký|kết\s+quả|số\s+điện\s+thoại|email|địa\s+chỉ)\s+"
               r"(?:của\s+)?(?:sinh\s+viên|bạn|sv|học\s+viên)\s+(?:khác|tên)", re.I),
    re.compile(r"(?:hồ\s+sơ|điểm|thông\s+tin|nhật\s+ký|kết\s+quả)\s+của\s+(?:bạn\s+)?[A-ZĐ][a-zà-ỹ]+\s+[A-ZĐ]"),
)
_DECISION = (
    re.compile(r"(?:duyệt|phê\s+duyệt|chấp\s+thuận|đồng\s+ý|cho\s+phép|công\s+nhận)\s+(?:giúp\s+|cho\s+)?(?:em|tôi|mình)\b", re.I),
    re.compile(r"(?:em|tôi|mình)\s+(?:có\s+)?được\s+(?:gia\s+hạn|duyệt|công\s+nhận|miễn|hoãn|lùi)", re.I),
    re.compile(r"(?:cho|xin)\s+(?:em|tôi|mình)\s+(?:được\s+)?(?:gia\s+hạn|hoãn|lùi|dời)", re.I),
)


@dataclass
class GuardResult:
    refusal_reason: str = ""
    violation_type: str = ""
    decision_request: bool = False


def check_policy_query(query: str, own_student_code: str | None) -> GuardResult:
    try:
        guardrails.check_input(query)
    except GuardrailViolation as exc:
        return GuardResult("Yêu cầu chứa nội dung tìm cách vượt qua quy tắc của trợ lý.", exc.violation_type)
    for pattern in _INJECTION_VI:
        if pattern.search(query):
            return GuardResult("Yêu cầu chứa nội dung tìm cách vượt qua quy tắc của trợ lý.", "prompt_injection_vi")
    own = (own_student_code or "").lower()
    if any(code.lower() != own for code in _STUDENT_CODE.findall(query)):
        return GuardResult("Trợ lý không cung cấp thông tin của sinh viên khác.", "other_student_data")
    for pattern in _OTHER_STUDENT:
        if pattern.search(query):
            return GuardResult("Trợ lý không cung cấp thông tin của sinh viên khác.", "other_student_data")
    return GuardResult(decision_request=any(p.search(query) for p in _DECISION))
