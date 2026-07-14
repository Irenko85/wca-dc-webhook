from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.conftest import competition
from wca_notifier.repository import SQLiteRepository


class RepositoryMigrationTests(unittest.TestCase):
    def test_migrates_delivered_legacy_tracking_without_requeueing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "legacy.sqlite3"
            legacy_competition = competition()
            with sqlite3.connect(database_path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE competitions (
                        id TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        start_date TEXT NOT NULL,
                        end_date TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE registration_tracking (
                        comp_id TEXT PRIMARY KEY,
                        notified_upcoming INTEGER NOT NULL DEFAULT 0,
                        notified_open INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE TABLE spots_tracking (
                        comp_id TEXT PRIMARY KEY,
                        notified INTEGER NOT NULL DEFAULT 0,
                        last_count INTEGER,
                        spot_limit INTEGER
                    );
                    """
                )
                connection.execute(
                    """
                    INSERT INTO competitions (id, data, start_date, end_date)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        legacy_competition["id"],
                        json.dumps(legacy_competition),
                        legacy_competition["start_date"],
                        legacy_competition["end_date"],
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO registration_tracking
                    VALUES (?, 1, 1)
                    """,
                    (legacy_competition["id"],),
                )
                connection.execute(
                    """
                    INSERT INTO spots_tracking
                    VALUES (?, 1, 88, 100)
                    """,
                    (legacy_competition["id"],),
                )

            repository = SQLiteRepository(database_path)

            self.assertTrue(
                repository.event_exists("registration_upcoming:SantiagoOpen2026")
            )
            self.assertTrue(
                repository.event_exists("registration_open:SantiagoOpen2026")
            )
            self.assertTrue(repository.event_exists("spots_limited:SantiagoOpen2026"))
            self.assertEqual(repository.pending_deliveries(), [])


if __name__ == "__main__":
    unittest.main()
