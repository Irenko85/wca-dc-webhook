from __future__ import annotations

import unittest

from wca_notifier.config import ConfigError, Settings


class SettingsTests(unittest.TestCase):
    def test_uses_chile_defaults_and_infers_configured_channels(self) -> None:
        settings = Settings.from_env(
            {
                "DISCORD_WEBHOOK_URL": "https://discord.com/api/webhooks/example",
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_CHANNEL_ID": "channel",
            }
        )

        self.assertEqual(settings.country_iso2, "CL")
        self.assertEqual(settings.timezone_name, "America/Santiago")
        self.assertEqual(settings.notification_language, "es")
        self.assertEqual(settings.poll_interval_seconds, 3600)
        self.assertEqual(settings.registration_open_grace_minutes, 90)
        self.assertEqual(settings.enabled_channels, ("discord", "telegram"))

    def test_rejects_partial_telegram_configuration(self) -> None:
        with self.assertRaisesRegex(ConfigError, "TELEGRAM_CHANNEL_ID"):
            Settings.from_env({"TELEGRAM_BOT_TOKEN": "token"})

    def test_rejects_unknown_language(self) -> None:
        with self.assertRaisesRegex(ConfigError, "NOTIFICATION_LANGUAGE"):
            Settings.from_env(
                {
                    "DISCORD_WEBHOOK_URL": "https://discord.example/webhook",
                    "NOTIFICATION_LANGUAGE": "pt",
                }
            )

    def test_requires_registration_open_margin_beyond_polling_interval(self) -> None:
        with self.assertRaisesRegex(ConfigError, "REGISTRATION_OPEN_GRACE_MINUTES"):
            Settings.from_env(
                {
                    "DISCORD_WEBHOOK_URL": "https://discord.example/webhook",
                    "POLL_INTERVAL_SECONDS": "3600",
                    "REGISTRATION_OPEN_GRACE_MINUTES": "60",
                }
            )


if __name__ == "__main__":
    unittest.main()
