"""Seed dữ liệu demo VIN-15: `python -m scripts.seed` (DB phải trống)."""

from src.db import init_db, session_factory
from src.seed import DEMO_PASSWORD, seed_demo

if __name__ == "__main__":
    init_db()
    db = session_factory()()
    try:
        done = seed_demo(db)
    finally:
        db.close()
    print("Đã seed dữ liệu demo." if done else "DB đã có dữ liệu — bỏ qua.")
    print(f"Tài khoản: sv01..sv30, gv01..gv03, admin — mật khẩu {DEMO_PASSWORD}")
