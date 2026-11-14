"""Thông báo in-app (R10.5). Email để sau — xem Backlog."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.orm import Notification


def notify(db: Session, user_id: int | None, kind: str, title: str, body: str = "", link: str = "") -> None:
    if user_id is None:
        return
    db.add(Notification(user_id=user_id, kind=kind, title=title, body=body, link=link))
