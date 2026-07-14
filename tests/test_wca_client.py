from __future__ import annotations

import unittest
from datetime import date
from typing import Any

from wca_notifier.wca_client import RequestsWcaClient


class JsonResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class RecordingSession:
    def __init__(self, responses: list[JsonResponse]) -> None:
        self._responses = iter(responses)
        self.requests: list[tuple[str, int]] = []

    def get(self, url: str, *, timeout: int) -> JsonResponse:
        self.requests.append((url, timeout))
        return next(self._responses)


class RequestsWcaClientTests(unittest.TestCase):
    def test_fetches_configured_country_from_current_local_date(self) -> None:
        session = RecordingSession([JsonResponse([{"id": "Example2026"}])])
        client = RequestsWcaClient(
            session=session,
            timeout_seconds=12,
            today=lambda: date(2026, 7, 14),
        )

        competitions = client.list_competitions("NZ")

        self.assertEqual(competitions, [{"id": "Example2026"}])
        self.assertEqual(
            session.requests,
            [
                (
                    "https://www.worldcubeassociation.org/api/v0/competitions"
                    "?country_iso2=NZ&start=2026-07-14",
                    12,
                )
            ],
        )

    def test_counts_only_accepted_wcif_registrations(self) -> None:
        session = RecordingSession(
            [
                JsonResponse(
                    {
                        "persons": [
                            {"registration": {"status": "accepted"}},
                            {"registration": {"status": "pending"}},
                            {"registration": None},
                            {"name": "Staff member"},
                        ]
                    }
                )
            ]
        )
        client = RequestsWcaClient(
            session=session,
            timeout_seconds=10,
            today=lambda: date(2026, 7, 14),
        )

        count = client.accepted_competitor_count(
            "https://www.worldcubeassociation.org/competitions/Example2026"
        )

        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
