from __future__ import annotations

import logging
from datetime import tzinfo
from typing import Any, Protocol

from wca_notifier.events import NotificationEvent
from wca_notifier.i18n import MessageCatalog
from wca_notifier.notifications.error_logging import log_delivery_failure
from wca_notifier.notifications.formatting import discord_embed

logger = logging.getLogger(__name__)


class HttpClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any: ...


class DiscordChannel:
    name = "discord"

    def __init__(
        self,
        *,
        webhook_url: str,
        catalog: MessageCatalog,
        timezone: tzinfo,
        http: HttpClient,
        timeout_seconds: int,
    ) -> None:
        self._webhook_url = webhook_url
        self._catalog = catalog
        self._timezone = timezone
        self._http = http
        self._timeout_seconds = timeout_seconds

    def send(self, event: NotificationEvent) -> bool:
        payload = {
            "content": "@everyone",
            "embeds": [discord_embed(event, self._catalog, self._timezone)],
        }
        try:
            response = self._http.post(
                self._webhook_url,
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except Exception as error:
            log_delivery_failure(
                logger,
                channel="Discord",
                event_key=event.key,
                error=error,
            )
            return False
        return True
