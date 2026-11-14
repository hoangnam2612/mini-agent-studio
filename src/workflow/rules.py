"""Rule engine xác định (design.md §3.2) — luật khai báo trong YAML, check là hàm Python.

Không dùng `eval` chuỗi: mỗi `check` trong YAML phải là khóa của CHECKS.
Kết quả luôn kèm căn cứ quy chế để UI báo lỗi có trích dẫn (R2.5).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import yaml

from src.config import get_settings
from src.models.orm import Cohort, Internship

FIELD_LABELS = {
    "company_name": "Tên doanh nghiệp",
    "company_tax_code": "Mã số thuế",
    "position": "Vị trí thực tập",
    "job_description": "Mô tả công việc",
    "start_date": "Ngày bắt đầu",
    "end_date": "Ngày kết thúc",
    "mentor_name": "Người hướng dẫn tại DN",
    "mentor_email": "Email người hướng dẫn",
}


@dataclass
class RuleResult:
    rule_id: str
    passed: bool
    message: str = ""
    citation: dict = field(default_factory=dict)
    severity: str = "warning"
    milestone_id: int | None = None
    evidence: list = field(default_factory=list)


@lru_cache
def load_cohort_config(path: str | None = None) -> dict:
    with Path(path or get_settings().cohort_config).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------- validation (R2.4)

def _required_fields(i: Internship, cohort: Cohort, params: dict) -> tuple[bool, str]:
    missing = [FIELD_LABELS.get(f, f) for f in params.get("fields", []) if not getattr(i, f, None)]
    return (not missing, "Thiếu trường bắt buộc: " + ", ".join(missing) if missing else "")


def _end_after_start(i: Internship, cohort: Cohort, params: dict) -> tuple[bool, str]:
    if not (i.start_date and i.end_date):
        return True, ""  # required_fields báo thiếu
    return (i.end_date > i.start_date, "Ngày kết thúc phải sau ngày bắt đầu")


def _duration_weeks_gte(i: Internship, cohort: Cohort, params: dict) -> tuple[bool, str]:
    if not (i.start_date and i.end_date):
        return True, ""
    weeks = (i.end_date - i.start_date).days / 7
    minimum = params.get("min", cohort.min_weeks)
    return (weeks >= minimum, f"Thời lượng {weeks:.1f} tuần, quy chế yêu cầu tối thiểu {minimum} tuần")


def _within_window(i: Internship, cohort: Cohort, params: dict) -> tuple[bool, str]:
    if not (i.start_date and i.end_date):
        return True, ""
    ok = cohort.start_window <= i.start_date and i.end_date <= cohort.end_window
    return (
        ok,
        f"Thời gian thực tập phải nằm trong khung đợt {cohort.start_window:%d/%m/%Y} – {cohort.end_window:%d/%m/%Y}",
    )


VALIDATION_CHECKS: dict[str, Callable[[Internship, Cohort, dict], tuple[bool, str]]] = {
    "required_fields": _required_fields,
    "end_after_start": _end_after_start,
    "duration_weeks_gte": _duration_weeks_gte,
    "within_window": _within_window,
}


def validate_internship(internship: Internship, cohort: Cohort) -> list[RuleResult]:
    results = []
    for rule in cohort.rules.get("validation", []):
        passed, message = VALIDATION_CHECKS[rule["check"]](internship, cohort, rule.get("params", {}))
        results.append(RuleResult(rule["id"], passed, "" if passed else message, rule.get("citation", {})))
    return results


# ---------------------------------------------------------------- monitor (R10.2)

_OPEN_MILESTONE = ("pending", "rejected", "overdue")


def _due_within(i: Internship, today: date, params: dict) -> list[RuleResult]:
    days = params.get("days", 3)
    out = []
    for m in i.milestones:
        remaining = (m.due_date - today).days
        if m.status in ("pending", "rejected") and 0 <= remaining <= days:
            out.append(RuleResult(
                "due_soon", False, f"Mốc '{m.name}' đến hạn sau {remaining} ngày ({m.due_date:%d/%m/%Y}) mà chưa nộp",
                milestone_id=m.id, evidence=[f"milestone:{m.id}"],
            ))
    return out


def _overdue(i: Internship, today: date, params: dict) -> list[RuleResult]:
    return [
        RuleResult(
            "overdue", False, f"Mốc '{m.name}' đã quá hạn {(today - m.due_date).days} ngày ({m.due_date:%d/%m/%Y})",
            milestone_id=m.id, evidence=[f"milestone:{m.id}"],
        )
        for m in i.milestones
        if m.status in _OPEN_MILESTONE and m.due_date < today
    ]


def _evidence_missing(i: Internship, today: date, params: dict) -> list[RuleResult]:
    labels = load_cohort_config().get("evidence_types", {})
    out = []
    for m in i.milestones:
        if m.status != "submitted" or not m.required_evidence:
            continue
        have = {e.evidence_type for e in m.evidence}
        missing = [t for t in m.required_evidence if t not in have]
        if missing:
            out.append(RuleResult(
                "missing_evidence", False,
                f"Mốc '{m.name}' đã nộp nhưng thiếu minh chứng: " + ", ".join(labels.get(t, t) for t in missing),
                milestone_id=m.id, evidence=[f"milestone:{m.id}"],
            ))
    return out


def _hours_below(i: Internship, today: date, params: dict) -> list[RuleResult]:
    if not i.start_date or i.status != "in_progress":
        return []
    weeks_elapsed = (min(today, i.end_date or today) - i.start_date).days // 7
    if weeks_elapsed < params.get("min_weeks_elapsed", 2):
        return []
    per_week = i.cohort.hours_per_week * (0.5 if i.mode == "part_time" else 1.0)
    expected = weeks_elapsed * per_week * params.get("tolerance", 0.8)
    logged = sum(log.hours for log in i.logs)
    if logged >= expected:
        return []
    return [RuleResult(
        "low_hours", False,
        f"Tổng giờ nhật ký {logged:g}h thấp hơn kỳ vọng {expected:g}h sau {weeks_elapsed} tuần",
        evidence=[f"internship:{i.id}/logs"],
    )]


MONITOR_CHECKS: dict[str, Callable[[Internship, date, dict], list[RuleResult]]] = {
    "milestone_due_within": _due_within,
    "milestone_overdue": _overdue,
    "evidence_types_missing": _evidence_missing,
    "cumulative_hours_below_expected": _hours_below,
}


def evaluate_monitor(internship: Internship, today: date) -> list[RuleResult]:
    findings: list[RuleResult] = []
    for rule in internship.cohort.rules.get("monitor", []):
        for result in MONITOR_CHECKS[rule["check"]](internship, today, rule.get("params", {})):
            result.rule_id = rule["id"]
            result.severity = rule.get("severity", "warning")
            findings.append(result)
    return findings


def milestone_due_date(anchor: str, offset_days: int, start: date, end: date) -> date:
    base = {"start": start, "end": end, "mid": start + (end - start) / 2}[anchor]
    return base + timedelta(days=offset_days)
