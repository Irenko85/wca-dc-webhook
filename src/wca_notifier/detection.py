from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any


def _parse_wca_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _has_started(competition: dict[str, Any], now: datetime) -> bool:
    start_date = datetime.strptime(competition["start_date"], "%Y-%m-%d").date()
    return start_date <= now.date()


def _registration_is_open(competition: dict[str, Any], now: datetime) -> bool:
    registration_open = competition.get("registration_open")
    registration_close = competition.get("registration_close")
    if not registration_open or not registration_close:
        return False
    return (
        _parse_wca_datetime(registration_open)
        <= now
        < _parse_wca_datetime(registration_close)
    )


def detect_registration_upcoming(
    competitions: Iterable[dict[str, Any]],
    *,
    now: datetime,
    window_minutes: int,
) -> list[dict[str, Any]]:
    """Return future competitions whose registration opens inside the window."""
    detected: list[dict[str, Any]] = []
    for competition in competitions:
        if _has_started(competition, now):
            continue
        registration_open = competition.get("registration_open")
        if not registration_open:
            continue
        opens_at = _parse_wca_datetime(registration_open)
        minutes_until_open = (opens_at - now).total_seconds() / 60
        if 0 < minutes_until_open <= window_minutes:
            detected.append(competition)
    return detected


def detect_registration_open(
    competitions: Iterable[dict[str, Any]],
    *,
    now: datetime,
    grace_minutes: int,
) -> list[dict[str, Any]]:
    """Return competitions whose registration opened inside the grace window."""
    detected: list[dict[str, Any]] = []
    for competition in competitions:
        if _has_started(competition, now) or not _registration_is_open(
            competition, now
        ):
            continue
        registration_open = competition.get("registration_open")
        if not registration_open:
            continue
        opened_at = _parse_wca_datetime(registration_open)
        minutes_since_open = (now - opened_at).total_seconds() / 60
        if 0 <= minutes_since_open <= grace_minutes:
            detected.append(competition)
    return detected


def detect_limited_spots(
    competitions: Iterable[dict[str, Any]],
    *,
    accepted_count: Callable[[str], int | None],
    threshold: float,
    now: datetime,
) -> list[dict[str, Any]]:
    """Return competitions whose accepted registrations reach the threshold."""
    detected: list[dict[str, Any]] = []
    for competition in competitions:
        if _has_started(competition, now) or not _registration_is_open(
            competition, now
        ):
            continue
        competitor_limit = competition.get("competitor_limit")
        if not competitor_limit:
            continue
        current_count = accepted_count(competition["url"])
        if current_count is None:
            continue
        percentage_filled = current_count / competitor_limit
        if percentage_filled >= threshold:
            detected.append(
                {
                    **competition,
                    "current_count": current_count,
                    "percentage_filled": percentage_filled,
                }
            )
    return detected
