"""Router VIN-15 — gắn dưới /api/v1 trong src/main.py."""

from fastapi import APIRouter

from src.api.vin15 import (
    admin_routes,
    assistant_routes,
    auth_routes,
    internship_routes,
    monitor_routes,
    progress_routes,
    summary_routes,
)

router = APIRouter()
for module in (auth_routes, internship_routes, progress_routes, assistant_routes, monitor_routes, admin_routes,
               summary_routes):
    router.include_router(module.router)
