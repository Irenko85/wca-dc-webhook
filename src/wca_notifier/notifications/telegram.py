from __future__ import annotations

import logging
from datetime import tzinfo
from typing import Any, Protocol

from wca_notifier.events import NotificationEvent
from wca_notifier.i18n import MessageCatalog
from wca_notifier.notifications.error_logging import log_delivery_failure
from wca_notifier.notifications.formatting import telegram_message

logger = logging.getLogger(__name__)


class HttpClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any: ...


class TelegramChannel:
    name = "telegram"

    def __init__(
        self,
        *,
        bot_token: str,
        channel_id: str,
        catalog: MessageCatalog,
        timezone: tzinfo,
        http: HttpClient,
        timeout_seconds: int,
    ) -> None:
        self._url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self._channel_id = channel_id
        self._catalog = catalog
        self._timezone = timezone
        self._http = http
        self._timeout_seconds = timeout_seconds

    def send(self, event: NotificationEvent) -> bool:
        payload = {
            "chat_id": self._channel_id,
            "text": telegram_message(event, self._catalog, self._timezone),
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        try:
            response = self._http.post(
                self._url,
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except Exception as error:
            log_delivery_failure(
                logger,
                channel="Telegram",
                event_key=event.key,
                error=error,
            )
            return False
        return True
