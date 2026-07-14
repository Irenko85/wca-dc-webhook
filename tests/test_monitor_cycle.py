from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tests.conftest import competition
from wca_notifier.monitor import run_cycle
from wca_notifier.repository import SQLiteRepository


@dataclass(frozen=True)
class Settings:
    country_iso2: str = "CL"
    registration_upcoming_minutes: int = 90
    registration_open_grace_minutes: int = 90
    spots_warning_percent: float = 0.8


class StubWcaClient:
    def __init__(
        self,
        competitions: list[dict[str, Any]],
        *,
        accepted_count: int = 0,
    ) -> None:
        self._competitions = competitions
        self._accepted_count = accepted_count

    def list_competitions(self, country_iso2: str) -> list[dict[str, Any]]:
        return self._competitions

    def accepted_competitor_count(self, competition_url: str) -> int:
        return self._accepted_count


class RecordingChannel:
    def __init__(self, name: str, outcomes: list[bool]) -> None:
        self.name = name
        self._outcomes = iter(outcomes)
        self.events: list[str] = []

    def send(self, event: Any) -> bool:
        self.events.append(event.key)
        return next(self._outcomes)


class MonitorCycleTests(unittest.TestCase):
    def test_failed_channel_retries_without_repeating_successful_channel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteRepository(Path(temporary_directory) / "state.sqlite3")
            client = StubWcaClient([competition()])
            discord = RecordingChannel("discord", [True])
            telegram = RecordingChannel("telegram", [False, True])
            now = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)

            run_cycle(Settings(), repository, client, [discord, telegram], now=now)
            run_cycle(Settings(), repository, client, [discord, telegram], now=now)

            self.assertEqual(discord.events, ["competition_new:SantiagoOpen2026"])
            self.assertEqual(
                telegram.events,
                [
                    "competition_new:SantiagoOpen2026",
                    "competition_new:SantiagoOpen2026",
                ],
            )

    def test_cycle_discovers_every_supported_event_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteRepository(Path(temporary_directory) / "state.sqlite3")
            client = StubWcaClient([competition()], accepted_count=80)
            discord = RecordingChannel("discord", [True, True, True, True])

            run_cycle(
                Settings(),
                repository,
                client,
                [discord],
                now=datetime(2026, 8, 1, 14, 0, tzinfo=UTC),
            )
            run_cycle(
                Settings(),
                repository,
                client,
                [discord],
                now=datetime(2026, 8, 1, 15, 30, tzinfo=UTC),
            )

            self.assertCountEqual(
                discord.events,
                [
                    "competition_new:SantiagoOpen2026",
                    "registration_upcoming:SantiagoOpen2026",
                    "registration_open:SantiagoOpen2026",
                    "spots_limited:SantiagoOpen2026",
                ],
            )

    def test_open_registration_replaces_a_stale_pending_reminder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SQLiteRepository(Path(temporary_directory) / "state.sqlite3")
            repository.save_competitions([competition()])
            client = StubWcaClient([competition()])
            telegram = RecordingChannel("telegram", [False, True])

            run_cycle(
                Settings(),
                repository,
                client,
                [telegram],
                now=datetime(2026, 8, 1, 14, 0, tzinfo=UTC),
            )
            run_cycle(
                Settings(),
                repository,
                client,
                [telegram],
                now=datetime(2026, 8, 1, 15, 30, tzinfo=UTC),
            )

            self.assertEqual(
                telegram.events,
                [
                    "registration_upcoming:SantiagoOpen2026",
                    "registration_open:SantiagoOpen2026",
                ],
            )


if __name__ == "__main__":
    unittest.main()
