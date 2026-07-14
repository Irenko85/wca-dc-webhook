from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Protocol

from wca_notifier.detection import (
    detect_limited_spots,
    detect_registration_open,
    detect_registration_upcoming,
)
from wca_notifier.events import NotificationEvent
from wca_notifier.repository import SQLiteRepository

logger = logging.getLogger(__name__)


class WcaClient(Protocol):
    def list_competitions(self, country_iso2: str) -> list[dict[str, Any]]: ...

    def accepted_competitor_count(self, competition_url: str) -> int: ...


class NotificationChannel(Protocol):
    name: str

    def send(self, event: NotificationEvent) -> bool: ...


def run_cycle(
    settings: Any,
    repository: SQLiteRepository,
    wca_client: WcaClient,
    channels: Iterable[NotificationChannel],
    *,
    now: datetime,
) -> None:
    """Discover notification events and deliver each channel independently."""
    configured_channels = {channel.name: channel for channel in channels}
    competitions = wca_client.list_competitions(settings.country_iso2)
    known_ids = repository.known_competition_ids()

    for competition in competitions:
        if competition["id"] not in known_ids:
            repository.enqueue(
                NotificationEvent.competition_new(competition),
                configured_channels,
            )

    event_groups = (
        (
            "registration_upcoming",
            detect_registration_upcoming(
                competitions,
                now=now,
                window_minutes=settings.registration_upcoming_minutes,
            ),
        ),
        (
            "registration_open",
            detect_registration_open(
                competitions,
                now=now,
                grace_minutes=settings.registration_open_grace_minutes,
            ),
        ),
        (
            "spots_limited",
            detect_limited_spots(
                [
                    competition
                    for competition in competitions
                    if not repository.event_exists(f"spots_limited:{competition['id']}")
                ],
                accepted_count=wca_client.accepted_competitor_count,
                threshold=settings.spots_warning_percent,
                now=now,
            ),
        ),
    )
    for event_type, detected_competitions in event_groups:
        for competition in detected_competitions:
            context: dict[str, Any] = {}
            if event_type == "registration_upcoming":
                opens_at = datetime.fromisoformat(
                    competition["registration_open"].replace("Z", "+00:00")
                )
                context["minutes"] = max(0, int((opens_at - now).total_seconds() / 60))
            elif event_type == "registration_open":
                repository.suppress_pending_event(
                    f"registration_upcoming:{competition['id']}"
                )
            repository.enqueue(
                NotificationEvent.for_competition(
                    event_type,
                    competition,
                    **context,
                ),
                configured_channels,
            )

    repository.save_competitions(competitions)

    for delivery in repository.pending_deliveries():
        channel = configured_channels.get(delivery.channel)
        if channel is None:
            continue
        try:
            delivered = channel.send(delivery.event)
        except Exception:
            logger.exception(
                "Notification delivery failed for %s via %s",
                delivery.event.key,
                delivery.channel,
            )
            delivered = False
        if delivered:
            repository.mark_delivered(delivery.event.key, delivery.channel)
