import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.api.vin15 import router as vin15_router
from src.config import get_settings
from src.db import init_db, init_engine, session_factory
from src.workflow.state_machine import TransitionError

logger = logging.getLogger("vin15")
_ROOT = Path(__file__).resolve().parent.parent
# Ưu tiên bản React đã build (frontend/dist); chưa build thì dùng FE cũ ở web/.
WEB_DIR = _ROOT / "frontend" / "dist" if (_ROOT / "frontend" / "dist" / "index.html").exists() else _ROOT / "web"


def guard_tracing() -> bool:
    """Tắt LangSmith tracing nếu không có key thật (R15.5: không gửi dữ liệu ra bên thứ ba ngoài ý muốn).

    `.env.example` của template từng để LANGCHAIN_TRACING_V2=true kèm key mẫu → app cố gửi trace
    (chứa prompt + ngữ cảnh sinh viên) tới api.smith.langchain.com. Trả True nếu tracing còn bật.
    """
    enabled = any(os.environ.get(k, "").lower() == "true" for k in ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"))
    key = os.environ.get("LANGCHAIN_API_KEY") or os.environ.get("LANGSMITH_API_KEY") or ""
    if enabled and (not key.strip() or key.startswith("your-")):
        for k in ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING"):
            os.environ[k] = "false"
        logger.warning("LangSmith tracing đã tắt: không có LANGCHAIN_API_KEY thật")
        return False
    return enabled


guard_tracing()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    init_engine()
    init_db()
    if settings.seed_demo_data:
        from src.seed import seed_demo

        db = session_factory()()
        try:
            seed_demo(db)
        finally:
            db.close()
    task = None
    if settings.monitor_enabled:
        from src.services.monitor import scheduler_loop

        task = asyncio.create_task(scheduler_loop())
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    print("Shutting down...")


app = FastAPI(
    title="VIN-15 — Hệ thống hỗ trợ thực tập bằng AI",
    description="Cổng thực tập Sinh viên – Giảng viên với trợ lý chính sách có trích dẫn (template AI20K)",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(TransitionError)
async def transition_error_handler(request: Request, exc: TransitionError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


app.include_router(router, prefix="/api/v1")
app.include_router(vin15_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
