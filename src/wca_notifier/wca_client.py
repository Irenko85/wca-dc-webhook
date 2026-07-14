from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class HttpSession(Protocol):
    def get(self, url: str, *, timeout: int) -> Any: ...


class RequestsWcaClient:
    def __init__(
        self,
        *,
        session: HttpSession,
        timeout_seconds: int,
        today: Callable[[], date],
    ) -> None:
        self._session = session
        self._timeout_seconds = timeout_seconds
        self._today = today

    def list_competitions(self, country_iso2: str) -> list[dict[str, Any]]:
        start_date = self._today().isoformat()
        url = (
            "https://www.worldcubeassociation.org/api/v0/competitions"
            f"?country_iso2={country_iso2}&start={start_date}"
        )
        response = self._session.get(url, timeout=self._timeout_seconds)
        response.raise_for_status()
        competitions = response.json()
        logger.info(
            "Fetched %d WCA competitions for %s",
            len(competitions),
            country_iso2,
        )
        return competitions

    def accepted_competitor_count(self, competition_url: str) -> int | None:
        competition_id = competition_url.rstrip("/").split("/")[-1]
        url = (
            "https://www.worldcubeassociation.org/api/v0/competitions/"
            f"{competition_id}/wcif/public"
        )
        try:
            response = self._session.get(url, timeout=self._timeout_seconds)
            response.raise_for_status()
            persons = response.json().get("persons", [])
        except Exception:
            logger.exception(
                "Could not fetch accepted competitors for %s", competition_id
            )
            return None

        return sum(
            1
            for person in persons
            if (person.get("registration") or {}).get("status") == "accepted"
        )
