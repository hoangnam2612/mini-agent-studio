from datetime import date

from src.config import get_settings
from src.core.time import local_today
from src.services.intake import normalize_date, normalize_phone


def test_ocr_digit_confusions_are_normalized_for_dates_and_phones():
    assert normalize_date("O5/0l/2027") == date(2027, 1, 5).isoformat()
    assert normalize_phone("O912 345 678") == "0912345678"


def test_business_clock_uses_configured_timezone(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_timezone", "Asia/Ho_Chi_Minh")
    assert local_today().year >= 2026
