from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from wca_notifier.events import NotificationEvent, PendingDelivery


class SQLiteRepository:
    """Persist observed competitions and per-channel notification deliveries."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS competitions (
                    id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS notification_events (
                    event_key TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    competition_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS notification_deliveries (
                    event_key TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    delivered_at TEXT,
                    PRIMARY KEY (event_key, channel),
                    FOREIGN KEY (event_key)
                        REFERENCES notification_events(event_key)
                        ON DELETE CASCADE
                );
                """
            )
            self._migrate_legacy_tracking(connection)

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def _migrate_legacy_tracking(self, connection: sqlite3.Connection) -> None:
        if self._table_exists(connection, "registration_tracking"):
            rows = connection.execute(
                """
                SELECT r.comp_id, r.notified_upcoming, r.notified_open, c.data
                FROM registration_tracking r
                JOIN competitions c ON c.id = r.comp_id
                """
            ).fetchall()
            for _competition_id, upcoming, opened, data in rows:
                competition = json.loads(data)
                if upcoming:
                    self._record_legacy_delivery(
                        connection,
                        NotificationEvent.for_competition(
                            "registration_upcoming", competition
                        ),
                    )
                if opened:
                    self._record_legacy_delivery(
                        connection,
                        NotificationEvent.for_competition(
                            "registration_open", competition
                        ),
                    )

        if self._table_exists(connection, "spots_tracking"):
            rows = connection.execute(
                """
                SELECT s.comp_id, s.notified, s.last_count, s.spot_limit, c.data
                FROM spots_tracking s
                JOIN competitions c ON c.id = s.comp_id
                WHERE s.notified = 1
                """
            ).fetchall()
            for _competition_id, _, last_count, spot_limit, data in rows:
                competition = json.loads(data)
                if last_count is not None and spot_limit:
                    competition.update(
                        current_count=last_count,
                        percentage_filled=last_count / spot_limit,
                    )
                self._record_legacy_delivery(
                    connection,
                    NotificationEvent.for_competition("spots_limited", competition),
                )

    @staticmethod
    def _record_legacy_delivery(
        connection: sqlite3.Connection, event: NotificationEvent
    ) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO notification_events (
                event_key, event_type, competition_id, payload
            ) VALUES (?, ?, ?, ?)
            """,
            (
                event.key,
                event.type,
                event.competition["id"],
                json.dumps(
                    {
                        "competition": event.competition,
                        "context": event.context,
                    }
                ),
            ),
        )
        for channel in ("discord", "telegram"):
            connection.execute(
                """
                INSERT OR IGNORE INTO notification_deliveries (
                    event_key, channel, delivered_at
                ) VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (event.key, channel),
            )

    def known_competition_ids(self) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT id FROM competitions").fetchall()
        return {row[0] for row in rows}

    def event_exists(self, event_key: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM notification_events WHERE event_key = ?",
                (event_key,),
            ).fetchone()
        return row is not None

    def save_competitions(self, competitions: Iterable[dict[str, Any]]) -> None:
        with self._connect() as connection:
            for competition in competitions:
                connection.execute(
                    """
                    INSERT INTO competitions (id, data, start_date, end_date)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        data = excluded.data,
                        start_date = excluded.start_date,
                        end_date = excluded.end_date,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        competition["id"],
                        json.dumps(competition),
                        competition["start_date"],
                        competition["end_date"],
                    ),
                )

    def enqueue(self, event: NotificationEvent, channel_names: Iterable[str]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO notification_events (
                    event_key, event_type, competition_id, payload
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    event.key,
                    event.type,
                    event.competition["id"],
                    json.dumps(
                        {
                            "competition": event.competition,
                            "context": event.context,
                        }
                    ),
                ),
            )
            for channel_name in channel_names:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO notification_deliveries (
                        event_key, channel
                    ) VALUES (?, ?)
                    """,
                    (event.key, channel_name),
                )

    def pending_deliveries(self) -> list[PendingDelivery]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT e.event_key, e.event_type, e.payload, d.channel
                FROM notification_events e
                JOIN notification_deliveries d USING (event_key)
                WHERE d.delivered_at IS NULL
                ORDER BY e.created_at, e.event_key, d.channel
                """
            ).fetchall()

        deliveries: list[PendingDelivery] = []
        for event_key, event_type, payload, channel in rows:
            event_payload = json.loads(payload)
            deliveries.append(
                PendingDelivery(
                    event=NotificationEvent(
                        key=event_key,
                        type=event_type,
                        competition=event_payload["competition"],
                        context=event_payload.get("context", {}),
                    ),
                    channel=channel,
                )
            )
        return deliveries

    def mark_delivered(self, event_key: str, channel: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE notification_deliveries
                SET delivered_at = CURRENT_TIMESTAMP
                WHERE event_key = ? AND channel = ?
                """,
                (event_key, channel),
            )

    def suppress_pending_event(self, event_key: str) -> None:
        """Close an obsolete event without delivering its pending channels."""
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE notification_deliveries
                SET delivered_at = CURRENT_TIMESTAMP
                WHERE event_key = ? AND delivered_at IS NULL
                """,
                (event_key,),
            )
