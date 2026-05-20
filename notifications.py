"""Notification and formatting functions for WCA competition tracking."""

import requests
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from config import (
    DISCORD_WEBHOOK_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
    REQUEST_TIMEOUT,
    EVENTS,
    EMBED_COLORS,
)

logger = logging.getLogger(__name__)


def get_competition_status(comp: Dict[str, Any]) -> str:
    """Determine if a competition is upcoming or ongoing."""
    today = datetime.now().date()
    start_date = datetime.strptime(comp["start_date"], "%Y-%m-%d").date()
    end_date = datetime.strptime(comp["end_date"], "%Y-%m-%d").date()

    if today < start_date:
        return "upcoming"
    elif start_date <= today <= end_date:
        return "ongoing"
    else:
        return "past"


def format_competition_info(comp: Dict[str, Any]) -> Dict[str, str]:
    """
    Format competition information into a standardized dictionary.

    Args:
        comp: Competition dictionary from WCA API

    Returns:
        Dictionary with formatted competition information
    """

    # Format dates
    start_date = comp["start_date"]
    end_date = comp["end_date"]

    start_date_fmt = datetime.strptime(start_date, "%Y-%m-%d").strftime(
        "%d/%m/%Y"
    )
    end_date_fmt = datetime.strptime(end_date, "%Y-%m-%d").strftime("%d/%m/%Y")

    # Handle multi-day competitions
    if start_date == end_date:
        date_text = f"📅 **Fecha:** {start_date_fmt}"
        date_text_plain = f"📅 Fecha: {start_date_fmt}"
    else:
        days = (
            datetime.strptime(end_date, "%Y-%m-%d")
            - datetime.strptime(start_date, "%Y-%m-%d")
        ).days + 1
        date_text = f"📅 **Fechas:** {start_date_fmt} → {end_date_fmt} ({days} días)"
        date_text_plain = f"📅 Fechas: {start_date_fmt} → {end_date_fmt}"

    # Format registration information
    reg_info = ""
    reg_info_plain = ""
    if comp.get("registration_open") and comp.get("registration_close"):
        reg_open = datetime.strptime(
            comp["registration_open"], "%Y-%m-%dT%H:%M:%S.%fZ"
        ).strftime("%d/%m/%Y")
        reg_close = datetime.strptime(
            comp["registration_close"], "%Y-%m-%dT%H:%M:%S.%fZ"
        ).strftime("%d/%m/%Y")
        reg_info = f"📝 **Registro:** {reg_open} → {reg_close}\n"
        reg_info_plain = f"📝 Registro: {reg_open} → {reg_close}\n"

    # Format events
    event_ids = comp.get("event_ids", [])
    event_names = [EVENTS.get(event_id, event_id) for event_id in event_ids]
    events_text = (
        ", ".join(event_names) if event_names else "No hay eventos disponibles"
    )

    # Format competitors limit
    limit_info = ""
    limit_info_plain = ""
    if comp.get("competitor_limit"):
        limit_info = f"👥 **Límite de competidores:** {comp['competitor_limit']}\n"
        limit_info_plain = f"👥 Límite de competidores: {comp['competitor_limit']}\n"

    # Get competition status
    status = get_competition_status(comp)
    status_emoji = ""
    if status == "ongoing":
        status_emoji = "🔴 EN CURSO: "

    return {
        "name": comp["name"],
        "city": comp.get("city", "No disponible"),
        "url": comp["url"],
        "date_text": date_text,
        "date_text_plain": date_text_plain,
        "reg_info": reg_info,
        "reg_info_plain": reg_info_plain,
        "events_text": events_text,
        "limit_info": limit_info,
        "limit_info_plain": limit_info_plain,
        "status": status,
        "status_emoji": status_emoji,
        "id": comp["id"],
        "country_code": comp.get("country", {}).get("iso2", "").lower(),
    }


def sort_competitions_by_date(
    competitions: List[Dict[str, Any]], reverse: bool = False
) -> List[Dict[str, Any]]:
    """
    Sort competitions by start date.

    Args:
        competitions: List of competition dictionaries
        reverse: If True, sort from furthest to soonest (default: False, soonest first)

    Returns:
        Sorted list of competition dictionaries
    """
    # Sort competitions by start_date
    return sorted(
        competitions,
        key=lambda comp: datetime.strptime(comp["start_date"], "%Y-%m-%d"),
        reverse=reverse,
    )


def create_notification_header(
    competitions: List[Dict[str, Any]], is_new: bool = False
) -> Dict[str, str]:
    """
    Create header texts for notifications.

    Args:
        competitions: List of competition dictionaries
        is_new: Whether these are newly detected competitions

    Returns:
        Dictionary with header texts for different platforms
    """
    comp_count = len(competitions)
    plural_suffix = "s" if comp_count > 1 else ""

    if is_new:
        discord_header = f"🎉 @everyone **¡{comp_count} nuevo{plural_suffix} torneo{plural_suffix}!**"
        telegram_header = f"🎉 **¡Nuevo torneo!**"
    else:
        discord_header = (
            f"📋 **Recordatorio: {comp_count} torneo{plural_suffix} próximamente**"
        )
        telegram_header = (
            f"📋 **Recordatorio: {comp_count} torneo{plural_suffix} próximamente**"
        )

    return {"discord": discord_header, "telegram": telegram_header}


def create_discord_embeds(
    competitions: List[Dict[str, Any]], is_new: bool = False
) -> List[Dict[str, Any]]:
    """Generate Discord embeds for competitions.

    Args:
        competitions: List of competition dictionaries
        is_new: Whether these are newly detected competitions

    Returns:
        List of Discord embed dictionaries
    """
    embeds = []

    for comp in competitions:
        comp_info = format_competition_info(comp)

        # Set color based on status and whether it's new
        color = (
            EMBED_COLORS["new"]
            if is_new
            else EMBED_COLORS.get(comp_info["status"], EMBED_COLORS["upcoming"])
        )

        # Add "NEW" prefix if it's a new competition
        title_prefix = "✨ NUEVO: " if is_new else ""
        title = f"{title_prefix}{comp_info['status_emoji']}{comp_info['name']}"

        # Create embed
        embed = {
            "title": title,
            "description": (
                f"🌎 **Ciudad:** {comp_info['city']}\n"
                f"{comp_info['date_text']}\n"
                f"{comp_info['reg_info']}"
                f"{comp_info['limit_info']}"
                f"🎯 **Eventos:** {comp_info['events_text']}"
            ),
            "url": comp_info["url"],
            "color": color,
            "footer": {"text": f"WCA Competition ID: {comp_info['id']}"},
        }

        # Add thumbnail if country code is available
        if comp_info["country_code"]:
            embed["thumbnail"] = {
                "url": f"https://flagcdn.com/w80/{comp_info['country_code']}.png"
            }

        embeds.append(embed)

    return embeds


def create_telegram_message(competition: Dict[str, Any], header: str) -> str:
    """
    Create a formatted Telegram message for a single competition.

    Args:
        competition: Competition dictionary
        header: Notification header text

    Returns:
        Formatted Telegram message
    """
    comp_info = format_competition_info(competition)

    return (
        f"{header}\n\n"
        f"🏆 *{comp_info['name']}*\n"
        f"🌍 Ciudad: {comp_info['city']}\n"
        f"{comp_info['date_text_plain']}\n"
        f"{comp_info['reg_info_plain']}"
        f"{comp_info['limit_info_plain']}"
        f"🎯 Eventos: {comp_info['events_text']}\n"
        f"🔗 [Más información]({comp_info['url']})"
    )


def send_discord_notification(
    competitions: List[Dict[str, Any]], is_new: bool = False
) -> bool:
    """Send a notification to Discord about competitions.

    Args:
        competitions: List of competition dictionaries
        is_new: Whether these are newly detected competitions

    Returns:
        True if notification was sent successfully, False otherwise
    """
    if not competitions:
        logger.info("No competitions to notify. Skipping Discord notification.")
        return False

    if not DISCORD_WEBHOOK_URL:
        logger.error("Discord webhook URL not configured. Cannot send notification.")
        return False

    # Sort competitions by start date
    sorted_comps = sort_competitions_by_date(competitions)

    embeds = create_discord_embeds(sorted_comps, is_new)
    header = create_notification_header(competitions, is_new)["discord"]

    # Discord has a limit of 10 embeds per webhook message
    # Split into batches if needed
    batch_size = 10
    for i in range(0, len(embeds), batch_size):
        batch_embeds = embeds[i : i + batch_size]

        # Adjust content for batched messages
        batch_content = header
        if i > 0:
            batch_content += f" (Parte {i//batch_size + 1})"

        data = {
            "content": batch_content,
            "embeds": batch_embeds,
        }

        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL, json=data, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            logger.info(
                f"Discord notification sent successfully ({len(batch_embeds)} competitions)"
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Discord notification: {e}")
            return False

    return True


def send_telegram_notification(
    competitions: List[Dict[str, Any]], is_new: bool = False
) -> bool:
    """Send a notification to Telegram about competitions.

    Args:
        competitions: List of competition dictionaries
        is_new: Whether these are newly detected competitions

    Returns:
        True if notification was sent successfully, False otherwise
    """
    if not competitions:
        logger.info("No competitions to notify. Skipping Telegram notification.")
        return False

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        logger.error("Telegram credentials not configured. Cannot send notification.")
        return False

    header = create_notification_header(competitions, is_new)["telegram"]
    sorted_comps = sort_competitions_by_date(competitions)  # Sort by start date

    for comp in sorted_comps:
        msg = create_telegram_message(comp, header)

        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error al enviar mensaje a Telegram: {e}")
            return False

    logger.info(
        f"Telegram notification sent successfully ({len(competitions)} competitions)"
    )

    return True


def send_registration_upcoming_notification(competition: Dict[str, Any]) -> bool:
    """Send notification that registration is opening soon for a single competition.

    Args:
        competition: Competition dictionary

    Returns:
        True if notification was sent successfully, False otherwise
    """
    comp_info = format_competition_info(competition)

    # Calculate time until registration opens
    now = datetime.now(timezone.utc)
    reg_open = datetime.strptime(
        competition["registration_open"], "%Y-%m-%dT%H:%M:%S.%fZ"
    ).replace(tzinfo=timezone.utc)
    minutes_until = int((reg_open - now).total_seconds() / 60)

    # Discord notification
    discord_success = False
    if DISCORD_WEBHOOK_URL:
        embed = {
            "title": f"⏰ ¡El registro abre pronto!",
            "description": (
                f"🏆 **{comp_info['name']}**\n\n"
                f"🌎 **Ciudad:** {comp_info['city']}\n"
                f"{comp_info['date_text']}\n"
                f"⏰ **El registro abre en ~{minutes_until} minutos**\n"
                f"{comp_info['limit_info']}"
                f"🎯 **Eventos:** {comp_info['events_text']}"
            ),
            "url": f"{comp_info['url']}/register",
            "color": 0xFFAA00,  # Orange
            "footer": {"text": f"WCA Competition ID: {comp_info['id']}"},
        }

        data = {"content": "@everyone", "embeds": [embed]}

        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL, json=data, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            logger.info(
                f"Discord notification sent: registration opening soon for {competition['name']}"
            )
            discord_success = True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Discord notification: {e}")

    # Telegram notification
    telegram_success = False
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID:
        msg = (
            f"⏰ *¡El registro abre pronto!*\n\n"
            f"🏆 *{comp_info['name']}*\n"
            f"🌍 Ciudad: {comp_info['city']}\n"
            f"{comp_info['date_text_plain']}\n"
            f"⏰ *El registro abre en ~{minutes_until} minutos*\n"
            f"{comp_info['limit_info_plain']}"
            f"🎯 Eventos: {comp_info['events_text']}\n"
            f"🔗 [Más información]({comp_info['url']})"
        )

        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            logger.info(
                f"Telegram notification sent: registration opening soon for {competition['name']}"
            )
            telegram_success = True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Telegram notification: {e}")

    return discord_success or telegram_success


def send_registration_open_notification(competition: Dict[str, Any]) -> bool:
    """Send notification that registration just opened for a single competition.

    Args:
        competition: Competition dictionary

    Returns:
        True if notification was sent successfully, False otherwise
    """
    comp_info = format_competition_info(competition)

    # Discord notification
    discord_success = False
    if DISCORD_WEBHOOK_URL:
        embed = {
            "title": f"🔔 ¡REGISTRO ABIERTO!",
            "description": (
                f"🏆 **{comp_info['name']}**\n\n"
                f"🌎 **Ciudad:** {comp_info['city']}\n"
                f"{comp_info['date_text']}\n"
                f"✅ **¡El registro está abierto AHORA!**\n"
                f"{comp_info['limit_info']}"
                f"🎯 **Eventos:** {comp_info['events_text']}"
            ),
            "url": f"{comp_info['url']}/register",
            "color": 0x00FF00,  # Green
            "footer": {"text": f"WCA Competition ID: {comp_info['id']}"},
        }

        data = {"content": "@everyone", "embeds": [embed]}

        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL, json=data, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            logger.info(
                f"Discord notification sent: registration open for {competition['name']}"
            )
            discord_success = True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Discord notification: {e}")

    # Telegram notification
    telegram_success = False
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID:
        msg = (
            f"🔔 *¡REGISTRO ABIERTO!*\n\n"
            f"🏆 *{comp_info['name']}*\n"
            f"🌍 Ciudad: {comp_info['city']}\n"
            f"{comp_info['date_text_plain']}\n"
            f"✅ *¡El registro está abierto AHORA!*\n"
            f"{comp_info['limit_info_plain']}"
            f"🎯 Eventos: {comp_info['events_text']}\n"
            f"🔗 [Registrarse aquí]({comp_info['url']})"
        )

        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            logger.info(
                f"Telegram notification sent: registration open for {competition['name']}"
            )
            telegram_success = True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Telegram notification: {e}")

    return discord_success or telegram_success


def send_limited_spots_notification(competition: Dict[str, Any]) -> bool:
    """Send notification that a competition is almost full.

    Args:
        competition: Competition dictionary with current_count and percentage_filled

    Returns:
        True if notification was sent successfully, False otherwise
    """
    comp_info = format_competition_info(competition)
    current_count = competition["current_count"]
    limit = competition["competitor_limit"]
    percentage = competition["percentage_filled"] * 100
    spots_left = limit - current_count

    # Discord notification
    discord_success = False
    if DISCORD_WEBHOOK_URL:
        embed = {
            "title": f"⚠️ ¡CUPOS LIMITADOS!",
            "description": (
                f"🏆 **{comp_info['name']}**\n\n"
                f"🌎 **Ciudad:** {comp_info['city']}\n"
                f"{comp_info['date_text']}\n"
                f"⚠️ **¡Quedan solo {spots_left} cupos disponibles!**\n"
                f"📊 **Inscritos:** {current_count}/{limit} ({percentage:.1f}%)\n"
                f"🎯 **Eventos:** {comp_info['events_text']}"
            ),
            "url": f"{comp_info['url']}/register",
            "color": 0xFF0000,  # Red
            "footer": {"text": f"WCA Competition ID: {comp_info['id']}"},
        }

        data = {"content": "@everyone", "embeds": [embed]}

        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL, json=data, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            logger.info(
                f"Discord notification sent: limited spots for {competition['name']}"
            )
            discord_success = True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Discord notification: {e}")

    # Telegram notification
    telegram_success = False
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID:
        msg = (
            f"⚠️ *¡CUPOS LIMITADOS!*\n\n"
            f"🏆 *{comp_info['name']}*\n"
            f"🌍 Ciudad: {comp_info['city']}\n"
            f"{comp_info['date_text_plain']}\n"
            f"⚠️ *¡Quedan solo {spots_left} cupos disponibles!*\n"
            f"📊 Inscritos: {current_count}/{limit} ({percentage:.1f}%)\n"
            f"🎯 Eventos: {comp_info['events_text']}\n"
            f"🔗 [Registrarse aquí]({comp_info['url']}/register)"
        )

        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            logger.info(
                f"Telegram notification sent: limited spots for {competition['name']}"
            )
            telegram_success = True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending Telegram notification: {e}")

    return discord_success or telegram_success
