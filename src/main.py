import asyncio
import logging
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
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


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
