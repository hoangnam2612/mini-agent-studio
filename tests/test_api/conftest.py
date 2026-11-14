"""Route demo của template giờ bắt buộc đăng nhập (VIN-15) — test cũ dùng user giả qua dependency override."""

import pytest

from src.core.auth import current_user
from src.main import app
from src.models.orm import User


@pytest.fixture(autouse=True)
def logged_in_user():
    app.dependency_overrides[current_user] = lambda: User(id=1, username="demo", role="student", full_name="Demo")
    yield
    app.dependency_overrides.pop(current_user, None)
