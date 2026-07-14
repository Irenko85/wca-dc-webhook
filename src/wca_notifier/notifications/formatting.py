from __future__ import annotations

import html
from datetime import datetime, tzinfo
from typing import Any

from wca_notifier.events import NotificationEvent
from wca_notifier.i18n import MessageCatalog

EVENT_NAMES = {
    "222": "2x2",
    "333": "3x3",
    "444": "4x4",
    "555": "5x5",
    "666": "6x6",
    "777": "7x7",
    "333bf": "3BLD",
    "333fm": "FMC",
    "333mbf": "Multi-Blind",
    "333oh": "OH",
    "clock": "Clock",
    "minx": "Megaminx",
    "pyram": "Pyraminx",
    "skewb": "Skewb",
    "sq1": "Square-1",
    "444bf": "4BLD",
    "555bf": "5BLD",
}


def _date(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")


def _date_time(value: str, timezone: tzinfo) -> str:
    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(timezone)
        .strftime("%d/%m/%Y")
    )


def competition_fields(
    competition: dict[str, Any], catalog: MessageCatalog, timezone: tzinfo
) -> dict[str, str]:
    start_date = _date(competition["start_date"])
    end_date = _date(competition["end_date"])
    date_text = start_date if start_date == end_date else f"{start_date} → {end_date}"

    registration_text = ""
    if competition.get("registration_open") and competition.get("registration_close"):
        registration_text = (
            f"{_date_time(competition['registration_open'], timezone)} → "
            f"{_date_time(competition['registration_close'], timezone)}"
        )

    event_names = [
        EVENT_NAMES.get(event_id, event_id)
        for event_id in competition.get("event_ids", [])
    ]
    return {
        "city": competition.get("city", "—"),
        "date": date_text,
        "registration": registration_text,
        "events": ", ".join(event_names) or catalog.text("fallback.no_events"),
    }


def discord_title(event: NotificationEvent, catalog: MessageCatalog) -> str:
    if event.type == "competition_new":
        badge = catalog.text("event.competition_new.badge")
        return f"✨ {badge}: {event.competition['name']}"
    return catalog.text(f"event.{event.type}.title")


def event_detail(event: NotificationEvent, catalog: MessageCatalog) -> str:
    competition = event.competition
    if event.type == "registration_upcoming":
        return catalog.text(
            "event.registration_upcoming.detail",
            minutes=event.context.get("minutes", 0),
        )
    if event.type == "registration_open":
        return catalog.text("event.registration_open.detail")
    if event.type == "spots_limited":
        spots_left = competition["competitor_limit"] - competition["current_count"]
        return catalog.text(
            "event.spots_limited.detail",
            spots_left=spots_left,
        )
    return ""


def discord_embed(
    event: NotificationEvent,
    catalog: MessageCatalog,
    timezone: tzinfo,
) -> dict[str, Any]:
    competition = event.competition
    fields = competition_fields(competition, catalog, timezone)
    description = [
        f"🌎 **{catalog.text('field.city')}:** {fields['city']}",
        f"📅 **{catalog.text('field.date')}:** {fields['date']}",
    ]
    if fields["registration"]:
        description.append(
            f"📝 **{catalog.text('field.registration')}:** {fields['registration']}"
        )
    if competition.get("competitor_limit"):
        description.append(
            f"👥 **{catalog.text('field.competitor_limit')}:** "
            f"{competition['competitor_limit']}"
        )
    detail = event_detail(event, catalog)
    if detail:
        description.append(f"⚡ **{detail}**")
    if event.type == "spots_limited":
        percentage = competition["percentage_filled"] * 100
        description.append(
            f"📊 **{catalog.text('field.registered')}:** "
            f"{competition['current_count']}/{competition['competitor_limit']} "
            f"({percentage:.1f}%)"
        )
    description.append(f"🎯 **{catalog.text('field.events')}:** {fields['events']}")

    colors = {
        "competition_new": 0x00FF00,
        "registration_upcoming": 0xFFAA00,
        "registration_open": 0x00FF00,
        "spots_limited": 0xFF0000,
    }
    target_url = competition["url"]
    if event.type in {"registration_upcoming", "registration_open", "spots_limited"}:
        target_url = f"{target_url}/register"

    embed: dict[str, Any] = {
        "title": discord_title(event, catalog),
        "description": "\n".join(description),
        "url": target_url,
        "color": colors[event.type],
        "footer": {"text": f"WCA Competition ID: {competition['id']}"},
    }
    country_code = competition.get("country_iso2") or competition.get(
        "country", {}
    ).get("iso2")
    if country_code:
        embed["thumbnail"] = {
            "url": f"https://flagcdn.com/w80/{country_code.lower()}.png"
        }
    return embed


def telegram_message(
    event: NotificationEvent,
    catalog: MessageCatalog,
    timezone: tzinfo,
) -> str:
    competition = event.competition
    fields = competition_fields(competition, catalog, timezone)
    if event.type == "competition_new":
        title = catalog.text("event.competition_new.title", count=1)
    else:
        title = catalog.text(f"event.{event.type}.title")

    lines = [
        (
            f"✨ <b>{html.escape(title)}</b>"
            if event.type == "competition_new"
            else f"⚠️ <b>{html.escape(title)}</b>"
        ),
        "",
        f"🏆 <b>{html.escape(str(competition['name']))}</b>",
        (
            f"🌍 {html.escape(catalog.text('field.city'))}: "
            f"{html.escape(fields['city'])}"
        ),
        (
            f"📅 {html.escape(catalog.text('field.date'))}: "
            f"{html.escape(fields['date'])}"
        ),
    ]
    if fields["registration"]:
        lines.append(
            f"📝 {html.escape(catalog.text('field.registration'))}: "
            f"{html.escape(fields['registration'])}"
        )
    detail = event_detail(event, catalog)
    if detail:
        lines.append(f"⚠️ <b>{html.escape(detail)}</b>")
    if competition.get("competitor_limit"):
        lines.append(
            f"👥 {html.escape(catalog.text('field.competitor_limit'))}: "
            f"{competition['competitor_limit']}"
        )
    if event.type == "spots_limited":
        percentage = competition["percentage_filled"] * 100
        lines.append(
            f"📊 {html.escape(catalog.text('field.registered'))}: "
            f"{competition['current_count']}/{competition['competitor_limit']} "
            f"({percentage:.1f}%)"
        )
    lines.append(
        f"🎯 {html.escape(catalog.text('field.events'))}: "
        f"{html.escape(fields['events'])}"
    )

    link_key = (
        "link.more_information" if event.type == "competition_new" else "link.register"
    )
    link_url = competition["url"]
    if event.type != "competition_new":
        link_url = f"{link_url}/register"
    lines.append(
        f'🔗 <a href="{html.escape(link_url, quote=True)}">'
        f"{html.escape(catalog.text(link_key))}</a>"
    )
    return "\n".join(lines)
