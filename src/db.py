"""Kết nối DB cho VIN-15 — SQLite (dev/test) hoặc Postgres (docker-compose).

Vì sao tồn tại: engine khởi tạo lười (lazy) để test thay bằng SQLite in-memory
qua `init_engine("sqlite://")` mà không phải sửa settings. `init_db()` tạo bảng
và trigger chặn UPDATE/DELETE trên `audit_event` (append-only, R12.5).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

_SQLITE_AUDIT_TRIGGERS = (
    """CREATE TRIGGER IF NOT EXISTS audit_event_no_update BEFORE UPDATE ON audit_event
       BEGIN SELECT RAISE(ABORT, 'audit_event is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS audit_event_no_delete BEFORE DELETE ON audit_event
       BEGIN SELECT RAISE(ABORT, 'audit_event is append-only'); END""",
)

_POSTGRES_AUDIT_TRIGGERS = (
    """CREATE OR REPLACE FUNCTION audit_event_append_only() RETURNS trigger AS $$
       BEGIN RAISE EXCEPTION 'audit_event is append-only'; END; $$ LANGUAGE plpgsql""",
    "DROP TRIGGER IF EXISTS audit_event_no_change ON audit_event",
    """CREATE TRIGGER audit_event_no_change BEFORE UPDATE OR DELETE ON audit_event
       FOR EACH ROW EXECUTE FUNCTION audit_event_append_only()""",
)


_ADDED_COLUMNS = {"policy_chunk": [("embedding", "JSON")]}


def _normalize_url(url: str) -> str:
    # Cho phép DATABASE_URL kiểu postgresql:// — dùng driver psycopg 3.
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def init_engine(url: str | None = None) -> Engine:
    """Tạo engine + session factory. Gọi lại để đổi DB (test dùng `sqlite://`)."""
    global _engine, _session_factory
    url = _normalize_url(url or get_settings().database_url)
    if url.startswith("sqlite"):
        kwargs: dict = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        else:
            db_path = url.split("sqlite:///", 1)[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(url, **kwargs)

        @event.listens_for(_engine, "connect")
        def _sqlite_fk(dbapi_conn, _record) -> None:
            # SQLite mặc định KHÔNG kiểm khóa ngoại → test sẽ lọt lỗi mà Postgres bắt được
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    else:
        _engine = create_engine(url, pool_pre_ping=True)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        init_engine()
    assert _engine is not None
    return _engine


def session_factory() -> sessionmaker[Session]:
    if _session_factory is None:
        init_engine()
    assert _session_factory is not None
    return _session_factory


def init_db() -> None:
    """Tạo bảng (không dùng Alembic ở phiên bản này) + trigger append-only cho audit."""
    from src.models import orm  # noqa: F401 — đăng ký model vào metadata

    engine = get_engine()
    Base.metadata.create_all(engine)
    statements = _SQLITE_AUDIT_TRIGGERS if engine.dialect.name == "sqlite" else _POSTGRES_AUDIT_TRIGGERS
    with engine.begin() as conn:
        # Chưa có Alembic: bổ sung cột thêm sau phiên bản đầu cho DB đã tồn tại
        existing = {c["name"] for c in inspect(conn).get_columns("policy_chunk")}
        for column, ddl_type in _ADDED_COLUMNS["policy_chunk"]:
            if column not in existing:
                conn.execute(text(f"ALTER TABLE policy_chunk ADD COLUMN {column} {ddl_type}"))
        for stmt in statements:
            conn.execute(text(stmt))


def get_db() -> Iterator[Session]:
    """FastAPI dependency — một session mỗi request, rollback nếu lỗi."""
    db = session_factory()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
