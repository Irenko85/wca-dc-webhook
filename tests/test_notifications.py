from __future__ import annotations

import io
import logging
import unittest
from typing import Any
from zoneinfo import ZoneInfo

from tests.conftest import competition
from wca_notifier.events import NotificationEvent
from wca_notifier.i18n import MessageCatalog
from wca_notifier.notifications.discord import DiscordChannel
from wca_notifier.notifications.telegram import TelegramChannel


class Response:
    def raise_for_status(self) -> None:
        return None


class RecordingHttpClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> Response:
        self.requests.append({"url": url, **kwargs})
        return Response()


class FailingResponse:
    def __init__(self, secret: str) -> None:
        self._secret = secret
        self.status_code = 400

    def raise_for_status(self) -> None:
        raise RuntimeError(f"request failed for {self._secret}")


class FailingHttpClient:
    def __init__(self, secret: str) -> None:
        self._secret = secret

    def post(self, url: str, **kwargs: Any) -> FailingResponse:
        return FailingResponse(self._secret)


class DiscordChannelTests(unittest.TestCase):
    def test_sends_localized_new_competition_embed(self) -> None:
        http = RecordingHttpClient()
        channel = DiscordChannel(
            webhook_url="https://discord.example/webhook",
            catalog=MessageCatalog.load("en"),
            timezone=ZoneInfo("America/Santiago"),
            http=http,
            timeout_seconds=10,
        )

        delivered = channel.send(NotificationEvent.competition_new(competition()))

        self.assertTrue(delivered)
        payload = http.requests[0]["json"]
        self.assertEqual(payload["content"], "@everyone")
        self.assertEqual(payload["embeds"][0]["title"], "✨ NEW: Santiago Open 2026")
        self.assertIn("🌎 **City:** Santiago", payload["embeds"][0]["description"])

    def test_formats_registration_dates_in_the_configured_timezone(self) -> None:
        http = RecordingHttpClient()
        channel = DiscordChannel(
            webhook_url="https://discord.example/webhook",
            catalog=MessageCatalog.load("en"),
            timezone=ZoneInfo("Pacific/Auckland"),
            http=http,
            timeout_seconds=10,
        )
        event = NotificationEvent.competition_new(
            competition(
                registration_open="2026-08-01T23:30:00.000Z",
                registration_close="2026-08-02T00:30:00.000Z",
            )
        )

        channel.send(event)

        description = http.requests[0]["json"]["embeds"][0]["description"]
        self.assertIn("**Registration:** 02/08/2026 → 02/08/2026", description)

    def test_does_not_log_the_webhook_secret_when_delivery_fails(self) -> None:
        secret = "https://discord.com/api/webhooks/123456789/secret-value"
        channel = DiscordChannel(
            webhook_url=secret,
            catalog=MessageCatalog.load("en"),
            timezone=ZoneInfo("America/Santiago"),
            http=FailingHttpClient(secret),
            timeout_seconds=10,
        )
        stream = io.StringIO()
        logger = logging.getLogger("wca_notifier.notifications.discord")
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        try:
            delivered = channel.send(NotificationEvent.competition_new(competition()))
        finally:
            logger.removeHandler(handler)

        self.assertFalse(delivered)
        self.assertNotIn(secret, stream.getvalue())


class TelegramChannelTests(unittest.TestCase):
    def test_sends_localized_limited_spots_message(self) -> None:
        http = RecordingHttpClient()
        channel = TelegramChannel(
            bot_token="token",
            channel_id="channel",
            catalog=MessageCatalog.load("es"),
            timezone=ZoneInfo("America/Santiago"),
            http=http,
            timeout_seconds=10,
        )
        limited_competition = competition(
            current_count=88,
            percentage_filled=0.88,
        )
        event = NotificationEvent.for_competition("spots_limited", limited_competition)

        delivered = channel.send(event)

        self.assertTrue(delivered)
        payload = http.requests[0]["json"]
        self.assertEqual(payload["chat_id"], "channel")
        self.assertIn("⚠️ <b>¡CUPOS LIMITADOS!</b>", payload["text"])
        self.assertIn("¡Quedan solo 12 cupos!", payload["text"])
        self.assertIn("📊 Inscritos: 88/100 (88.0%)", payload["text"])

    def test_escapes_wca_text_using_telegram_html(self) -> None:
        http = RecordingHttpClient()
        channel = TelegramChannel(
            bot_token="token",
            channel_id="channel",
            catalog=MessageCatalog.load("en"),
            timezone=ZoneInfo("Pacific/Auckland"),
            http=http,
            timeout_seconds=10,
        )
        event = NotificationEvent.competition_new(
            competition(
                name="A&B <Cube> [Open]",
                city="Wellington <Central>",
            )
        )

        delivered = channel.send(event)

        self.assertTrue(delivered)
        payload = http.requests[0]["json"]
        self.assertEqual(payload["parse_mode"], "HTML")
        self.assertIn("<b>A&amp;B &lt;Cube&gt; [Open]</b>", payload["text"])
        self.assertIn("Wellington &lt;Central&gt;", payload["text"])

    def test_does_not_log_the_bot_token_when_delivery_fails(self) -> None:
        secret = "123456789:super-secret-bot-token"
        channel = TelegramChannel(
            bot_token=secret,
            channel_id="channel",
            catalog=MessageCatalog.load("es"),
            timezone=ZoneInfo("America/Santiago"),
            http=FailingHttpClient(secret),
            timeout_seconds=10,
        )
        stream = io.StringIO()
        logger = logging.getLogger("wca_notifier.notifications.telegram")
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        try:
            delivered = channel.send(NotificationEvent.competition_new(competition()))
        finally:
            logger.removeHandler(handler)

        self.assertFalse(delivered)
        self.assertNotIn(secret, stream.getvalue())


if __name__ == "__main__":
    unittest.main()
