from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NotificationEvent:
    key: str
    type: str
    competition: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def competition_new(cls, competition: dict[str, Any]) -> NotificationEvent:
        return cls.for_competition("competition_new", competition)

    @classmethod
    def for_competition(
        cls,
        event_type: str,
        competition: dict[str, Any],
        **context: Any,
    ) -> NotificationEvent:
        return cls(
            key=f"{event_type}:{competition['id']}",
            type=event_type,
            competition=competition,
            context=context,
        )


@dataclass(frozen=True)
class PendingDelivery:
    event: NotificationEvent
    channel: str
