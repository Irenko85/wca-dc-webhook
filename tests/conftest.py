from __future__ import annotations

from typing import Any


def competition(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "id": "SantiagoOpen2026",
        "name": "Santiago Open 2026",
        "city": "Santiago",
        "country_iso2": "CL",
        "start_date": "2026-09-05",
        "end_date": "2026-09-06",
        "registration_open": "2026-08-01T15:00:00.000Z",
        "registration_close": "2026-08-20T15:00:00.000Z",
        "competitor_limit": 100,
        "event_ids": ["333", "222"],
        "url": "https://www.worldcubeassociation.org/competitions/SantiagoOpen2026",
    }
    value.update(overrides)
    return value
