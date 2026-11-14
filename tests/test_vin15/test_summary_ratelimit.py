"""Danh sách tổng hợp (R7) và giới hạn tần suất (đăng nhập, trợ lý)."""

from __future__ import annotations

import csv
import io

from openpyxl import load_workbook
from sqlalchemy import select

from src.config import get_settings
from src.core import ratelimit
from src.models.orm import AuditEvent, User
from tests.test_vin15.conftest import internship_of


async def test_r7_summary_columns_and_scope(api, db):
    r = await api.call("GET", "/internships-summary", "gv01")
    assert r.status_code == 200
    body = r.json()
    names = {row["student_name"] for row in body["items"]}
    gv01 = db.scalar(select(User).where(User.username == "gv01"))
    assert all(row["lecturer_id"] == gv01.id for row in body["items"])  # GV chỉ thấy SV của mình
    sv04 = next(row for row in body["items"] if row["id"] == internship_of(db, "sv04").id)
    assert sv04["open_flags"] >= 1 and sv04["max_severity"] == "warning"
    assert sv04["next_milestone"] and sv04["next_due"] and 0 <= sv04["progress_pct"] <= 100
    admin = (await api.call("GET", "/internships-summary", "admin")).json()
    assert admin["total"] > body["total"] and names <= {row["student_name"] for row in admin["items"]}
    assert (await api.call("GET", "/internships-summary", "sv03")).status_code == 403


async def test_r7_filters_sort_search_paging(api, db):
    admin = lambda **p: api.call("GET", "/internships-summary", "admin", params=p)  # noqa: E731
    flagged = (await admin(risk="any")).json()["items"]
    assert flagged and all(row["open_flags"] for row in flagged)
    assert all(not row["open_flags"] for row in (await admin(risk="none")).json()["items"])
    assert all(row["status"] == "in_progress" for row in (await admin(status="in_progress")).json()["items"])
    sv03 = internship_of(db, "sv03")
    assert [row["id"] for row in (await admin(q=sv03.student.student_code.lower())).json()["items"]] == [sv03.id]
    by_program = (await admin(program="Công nghệ thông tin")).json()["items"]
    assert by_program and all(row["program"] == "Công nghệ thông tin" for row in by_program)
    gv02 = db.scalar(select(User).where(User.username == "gv02"))
    assert all(row["lecturer_id"] == gv02.id for row in (await admin(lecturer_id=gv02.id)).json()["items"])
    names = [row["student_name"] for row in (await admin(sort="student", order="asc")).json()["items"]]
    assert names == sorted(names, key=str.lower)
    page = (await admin(page=2, page_size=2)).json()
    assert page["page"] == 2 and len(page["items"]) <= 2 and page["total"] == (await admin()).json()["total"]
    risk_sorted = (await admin(sort="risk", order="desc")).json()["items"]
    assert risk_sorted[0]["open_flags"] > 0


async def test_r7_export_csv_and_xlsx_respect_scope(api, db):
    r = await api.call("GET", "/internships-summary/export", "gv01", params={"format": "csv"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0][:2] == ["Mã SV", "Sinh viên"]
    listed = (await api.call("GET", "/internships-summary", "gv01")).json()["total"]
    assert len(rows) - 1 == listed
    text = r.content.decode("utf-8-sig")
    assert "@" not in text  # không xuất email/SĐT (R7.3: chỉ trường trong phạm vi bảng)

    r = await api.call("GET", "/internships-summary/export", "admin", params={"format": "xlsx", "risk": "any"})
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws.cell(1, 1).value == "Mã SV" and ws.max_row - 1 == (await api.call(
        "GET", "/internships-summary", "admin", params={"risk": "any"})).json()["total"]
    db.expire_all()
    assert db.scalar(select(AuditEvent).where(AuditEvent.action == "exported"))
    assert (await api.call("GET", "/internships-summary/export", "sv03")).status_code == 403


async def test_login_lockout_after_repeated_failures(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_max_failures", 3)
    bad = {"username": "sv05", "password": "sai"}
    for _ in range(3):
        assert (await api.client.post("/api/v1/auth/login", json=bad)).status_code == 401
    r = await api.client.post("/api/v1/auth/login", json={"username": "sv05", "password": "demo123"})
    assert r.status_code == 429 and "tạm khóa" in r.json()["detail"] and int(r.headers["Retry-After"]) > 0
    # Tài khoản khác không bị ảnh hưởng
    assert (await api.client.post("/api/v1/auth/login", json={"username": "sv06", "password": "demo123"})).status_code == 200


async def test_login_success_clears_failures(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_max_failures", 3)
    for _ in range(2):
        await api.client.post("/api/v1/auth/login", json={"username": "sv05", "password": "sai"})
    assert (await api.client.post("/api/v1/auth/login", json={"username": "sv05", "password": "demo123"})).status_code == 200
    for _ in range(2):
        await api.client.post("/api/v1/auth/login", json={"username": "sv05", "password": "sai"})
    assert (await api.client.post("/api/v1/auth/login", json={"username": "sv05", "password": "demo123"})).status_code == 200


async def test_login_ip_limit(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "login_ip_per_minute", 4)
    codes = [(await api.client.post("/api/v1/auth/login", json={"username": f"x{n}", "password": "y"})).status_code
             for n in range(6)]
    assert codes[:4] == [401] * 4 and codes[4:] == [429, 429]


async def test_assistant_usage_limit(api, monkeypatch):
    headers = await api.login("sv03")
    monkeypatch.setattr(get_settings(), "assistant_per_minute", 2)
    for _ in range(2):
        r = await api.client.post("/api/v1/assistant/chat", headers=headers, json={"message": "Khi nào nộp đề cương?"})
        assert r.status_code == 200
    r = await api.client.post("/api/v1/assistant/chat/stream", headers=headers, json={"message": "Khi nào nộp đề cương?"})
    assert r.status_code == 429


def test_sliding_window_expires():
    now = [0.0]
    w = ratelimit.SlidingWindow(clock=lambda: now[0])
    w.add("k")
    w.add("k")
    assert w.count("k", 60) == 2
    now[0] = 61
    assert w.count("k", 60) == 0
