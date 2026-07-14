from __future__ import annotations

import string
import unittest

from wca_notifier.i18n import MessageCatalog


def placeholders(template: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in string.Formatter().parse(template)
        if field_name
    }


class MessageCatalogTests(unittest.TestCase):
    def test_english_and_spanish_have_matching_keys_and_placeholders(self) -> None:
        english = MessageCatalog.load("en")
        spanish = MessageCatalog.load("es")

        self.assertEqual(english.keys(), spanish.keys())
        for key in english:
            self.assertEqual(
                placeholders(english.template(key)),
                placeholders(spanish.template(key)),
                key,
            )

    def test_renders_each_current_notification_event(self) -> None:
        catalog = MessageCatalog.load("en")

        self.assertEqual(
            catalog.text("event.competition_new.title", count=1),
            "1 new competition!",
        )
        self.assertEqual(
            catalog.text("event.registration_upcoming.detail", minutes=45),
            "Registration opens in ~45 minutes",
        )
        self.assertEqual(
            catalog.text("event.registration_open.detail"),
            "Registration is open now!",
        )
        self.assertEqual(
            catalog.text("event.spots_limited.detail", spots_left=12),
            "Only 12 spots left!",
        )


if __name__ == "__main__":
    unittest.main()
