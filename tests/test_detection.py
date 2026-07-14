from __future__ import annotations

import unittest
from datetime import UTC, datetime

from tests.conftest import competition
from wca_notifier.detection import (
    detect_limited_spots,
    detect_registration_open,
    detect_registration_upcoming,
)


class RegistrationUpcomingTests(unittest.TestCase):
    def test_detects_registration_inside_configured_window(self) -> None:
        now = datetime(2026, 8, 1, 14, 0, tzinfo=UTC)

        detected = detect_registration_upcoming(
            [competition()],
            now=now,
            window_minutes=90,
        )

        self.assertEqual([item["id"] for item in detected], ["SantiagoOpen2026"])


class RegistrationOpenTests(unittest.TestCase):
    def test_detects_registration_opened_inside_grace_window(self) -> None:
        now = datetime(2026, 8, 1, 15, 30, tzinfo=UTC)

        detected = detect_registration_open(
            [competition()],
            now=now,
            grace_minutes=60,
        )

        self.assertEqual([item["id"] for item in detected], ["SantiagoOpen2026"])


class LimitedSpotsTests(unittest.TestCase):
    def test_detects_competition_at_configured_occupancy(self) -> None:
        detected = detect_limited_spots(
            [competition()],
            accepted_count=lambda _: 80,
            threshold=0.8,
            now=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        )

        self.assertEqual(detected[0]["current_count"], 80)
        self.assertEqual(detected[0]["percentage_filled"], 0.8)

    def test_does_not_alert_for_a_competition_that_already_started(self) -> None:
        detected = detect_limited_spots(
            [competition(start_date="2026-07-14")],
            accepted_count=lambda _: 90,
            threshold=0.8,
            now=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
        )

        self.assertEqual(detected, [])

    def test_does_not_query_wcif_outside_registration_window(self) -> None:
        for now in (
            datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
            datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
        ):
            with self.subTest(now=now):
                queried_urls: list[str] = []

                detected = detect_limited_spots(
                    [competition()],
                    accepted_count=lambda url, calls=queried_urls: (
                        calls.append(url) or 90
                    ),
                    threshold=0.8,
                    now=now,
                )

                self.assertEqual(detected, [])
                self.assertEqual(queried_urls, [])


if __name__ == "__main__":
    unittest.main()
