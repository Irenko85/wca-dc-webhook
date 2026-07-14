from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

from wca_notifier.config import Settings
from wca_notifier.i18n import MessageCatalog
from wca_notifier.monitor import NotificationChannel, run_cycle
from wca_notifier.notifications.discord import DiscordChannel
from wca_notifier.notifications.telegram import TelegramChannel
from wca_notifier.repository import SQLiteRepository
from wca_notifier.wca_client import RequestsWcaClient

logger = logging.getLogger(__name__)
HEARTBEAT_PATH = Path("/tmp/wca-monitor-heartbeat")


class TimezoneFormatter(logging.Formatter):
    def __init__(self, timezone, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._timezone = timezone

    def formatTime(self, record, datefmt=None):
        timestamp = datetime.fromtimestamp(record.created, tz=self._timezone)
        if datefmt:
            return timestamp.strftime(datefmt)
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        TimezoneFormatter(
            settings.timezone,
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        )
    )
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def build_channels(
    settings: Settings,
    catalog: MessageCatalog,
    session: requests.Session,
) -> list[NotificationChannel]:
    channels: list[NotificationChannel] = []
    if settings.discord_enabled:
        channels.append(
            DiscordChannel(
                webhook_url=settings.discord_webhook_url or "",
                catalog=catalog,
                timezone=settings.timezone,
                http=session,
                timeout_seconds=settings.request_timeout_seconds,
            )
        )
    if settings.telegram_enabled:
        channels.append(
            TelegramChannel(
                bot_token=settings.telegram_bot_token or "",
                channel_id=settings.telegram_channel_id or "",
                catalog=catalog,
                timezone=settings.timezone,
                http=session,
                timeout_seconds=settings.request_timeout_seconds,
            )
        )
    return channels


def main() -> None:
    load_dotenv()
    settings = Settings.from_env()
    configure_logging(settings)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    repository = SQLiteRepository(settings.db_path)
    catalog = MessageCatalog.load(settings.notification_language)
    channels = build_channels(settings, catalog, session)
    wca_client = RequestsWcaClient(
        session=session,
        timeout_seconds=settings.request_timeout_seconds,
        today=lambda: datetime.now(settings.timezone).date(),
    )

    logger.info(
        "Starting WCA monitor for %s with channels: %s",
        settings.country_iso2,
        ", ".join(settings.enabled_channels),
    )
    while True:
        try:
            run_cycle(
                settings,
                repository,
                wca_client,
                channels,
                now=datetime.now(UTC),
            )
            HEARTBEAT_PATH.touch()
            logger.info("WCA monitoring cycle completed")
        except Exception:
            logger.exception("WCA monitoring cycle failed")
        time.sleep(settings.poll_interval_seconds)
