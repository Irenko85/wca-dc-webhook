from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ConfigError(ValueError):
    """Raised when runtime configuration is incomplete or invalid."""


def _positive_int(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        value = int(env.get(name, str(default)))
    except ValueError as error:
        raise ConfigError(f"{name} must be an integer") from error
    if value <= 0:
        raise ConfigError(f"{name} must be greater than zero")
    return value


def _ratio(env: Mapping[str, str], name: str, default: float) -> float:
    try:
        value = float(env.get(name, str(default)))
    except ValueError as error:
        raise ConfigError(f"{name} must be a number") from error
    if not 0 < value <= 1:
        raise ConfigError(f"{name} must be greater than 0 and at most 1")
    return value


def _optional_bool(env: Mapping[str, str], name: str, *, default: bool) -> bool:
    raw_value = env.get(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be true or false")


@dataclass(frozen=True)
class Settings:
    country_iso2: str
    timezone_name: str
    notification_language: str
    poll_interval_seconds: int
    registration_upcoming_minutes: int
    registration_open_grace_minutes: int
    spots_warning_percent: float
    request_timeout_seconds: int
    db_path: Path
    discord_webhook_url: str | None
    telegram_bot_token: str | None
    telegram_channel_id: str | None
    discord_enabled: bool
    telegram_enabled: bool

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def enabled_channels(self) -> tuple[str, ...]:
        channels: list[str] = []
        if self.discord_enabled:
            channels.append("discord")
        if self.telegram_enabled:
            channels.append("telegram")
        return tuple(channels)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        values = os.environ if env is None else env
        country_iso2 = values.get("WCA_COUNTRY_ISO2", "CL").strip().upper()
        if len(country_iso2) != 2 or not country_iso2.isalpha():
            raise ConfigError("WCA_COUNTRY_ISO2 must be a two-letter ISO2 code")

        timezone_name = values.get("TZ", "America/Santiago").strip()
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as error:
            raise ConfigError(f"TZ is not a valid timezone: {timezone_name}") from error

        notification_language = values.get("NOTIFICATION_LANGUAGE", "es").strip()
        if notification_language not in {"es", "en"}:
            raise ConfigError("NOTIFICATION_LANGUAGE must be 'es' or 'en'")

        discord_webhook_url = values.get("DISCORD_WEBHOOK_URL") or None
        telegram_bot_token = values.get("TELEGRAM_BOT_TOKEN") or None
        telegram_channel_id = values.get("TELEGRAM_CHANNEL_ID") or None
        discord_enabled = _optional_bool(
            values,
            "DISCORD_ENABLED",
            default=discord_webhook_url is not None,
        )
        telegram_enabled = _optional_bool(
            values,
            "TELEGRAM_ENABLED",
            default=telegram_bot_token is not None or telegram_channel_id is not None,
        )

        if discord_enabled and not discord_webhook_url:
            raise ConfigError("DISCORD_WEBHOOK_URL is required when Discord is enabled")
        if telegram_enabled and not telegram_bot_token:
            raise ConfigError("TELEGRAM_BOT_TOKEN is required when Telegram is enabled")
        if telegram_enabled and not telegram_channel_id:
            raise ConfigError(
                "TELEGRAM_CHANNEL_ID is required when Telegram is enabled"
            )
        if not discord_enabled and not telegram_enabled:
            raise ConfigError("At least one notification channel must be enabled")

        poll_interval_seconds = _positive_int(values, "POLL_INTERVAL_SECONDS", 3600)
        registration_open_grace_minutes = _positive_int(
            values, "REGISTRATION_OPEN_GRACE_MINUTES", 90
        )
        if registration_open_grace_minutes * 60 <= poll_interval_seconds:
            raise ConfigError(
                "REGISTRATION_OPEN_GRACE_MINUTES must be longer than "
                "POLL_INTERVAL_SECONDS"
            )

        return cls(
            country_iso2=country_iso2,
            timezone_name=timezone_name,
            notification_language=notification_language,
            poll_interval_seconds=poll_interval_seconds,
            registration_upcoming_minutes=_positive_int(
                values, "REGISTRATION_UPCOMING_MINUTES", 90
            ),
            registration_open_grace_minutes=registration_open_grace_minutes,
            spots_warning_percent=_ratio(values, "SPOTS_WARNING_PERCENT", 0.8),
            request_timeout_seconds=_positive_int(
                values, "REQUEST_TIMEOUT_SECONDS", 10
            ),
            db_path=Path(values.get("DB_PATH", "data/wca_tracker.sqlite3")),
            discord_webhook_url=discord_webhook_url,
            telegram_bot_token=telegram_bot_token,
            telegram_channel_id=telegram_channel_id,
            discord_enabled=discord_enabled,
            telegram_enabled=telegram_enabled,
        )
