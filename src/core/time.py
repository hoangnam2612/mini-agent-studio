"""Application-local clock helpers.

Business dates follow the configured application timezone, not the host UTC
clock. Keep the timezone conversion in one module so scheduled jobs and API
responses cannot drift apart.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from src.config import get_settings


def local_now() -> datetime:
    return datetime.now(UTC).astimezone(ZoneInfo(get_settings().app_timezone))


def local_today() -> date:
    return local_now().date()
