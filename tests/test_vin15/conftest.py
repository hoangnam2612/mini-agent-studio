"""Fixtures VIN-15: SQLite in-memory + seed demo mới cho MỖI test, client có helper đăng nhập."""

from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.config import get_settings
from src.db import init_db, init_engine, session_factory
from src.seed import seed_demo


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "openai_api_key", "")  # luôn chạy chế độ không LLM, xác định
    monkeypatch.setattr(settings, "enable_admin_role", True)
    # Test đăng nhập lại ở mỗi lời gọi — nới giới hạn; test giới hạn tự đặt lại giá trị thấp
    monkeypatch.setattr(settings, "login_ip_per_minute", 100_000)
    monkeypatch.setattr(settings, "assistant_per_minute", 100_000)
    from src.core import ratelimit

    ratelimit.reset_all()
    init_engine("sqlite://")
    init_db()
    db = session_factory()()
    seed_demo(db, date.today())
    db.close()
    yield


@pytest.fixture
def db():
    session = session_factory()()
    yield session
    session.close()


class Api:
    def __init__(self, client: AsyncClient):
        self.client = client

    async def login(self, username: str) -> dict:
        r = await self.client.post("/api/v1/auth/login", json={"username": username, "password": "demo123"})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['token']}"}

    async def call(self, method: str, path: str, user: str, **kwargs):
        headers = await self.login(user)
        return await self.client.request(method, "/api/v1" + path, headers=headers, **kwargs)


@pytest_asyncio.fixture
async def api():
    from src.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield Api(client)


def internship_of(db, username: str):
    from sqlalchemy import select

    from src.models.orm import Internship, User

    user = db.scalar(select(User).where(User.username == username))
    return db.scalar(select(Internship).where(Internship.student_id == user.id))
