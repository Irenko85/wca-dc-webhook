import os
import requests
import datetime
import json
import logging
from typing import List, Dict, Set, Optional, Any, Union
from pathlib import Path
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get Discord webhook URL from environment variables
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
if not DISCORD_WEBHOOK_URL:
    logger.warning("DISCORD_WEBHOOK_URL not found in environment variables!")

# Constants
PREV_COMPS_FILE = Path("prev_comps.json")
DEFAULT_COUNTRY = "CL"  # Chile as default country
REQUEST_TIMEOUT = 10  # seconds

# Dictionary for competition event categories
EVENTS = {
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

# Discord embed colors by competition status
EMBED_COLORS = {
    "new": 0x00FF00,  # Green
    "upcoming": 0x002C99,  # Blue
    "ongoing": 0xFF9900,  # Orange
}


def initialize_data_file() -> None:
    """Ensure prev_comps.json exists with valid JSON content."""
    try:
        if not PREV_COMPS_FILE.exists():
            logger.info(f"Creating empty {PREV_COMPS_FILE}")
            PREV_COMPS_FILE.write_text("[]")
        else:
            # Validate JSON
            with open(PREV_COMPS_FILE, "r") as file:
                json.load(file)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in {PREV_COMPS_FILE}. Creating new empty file.")
        PREV_COMPS_FILE.write_text("[]")
    except Exception as e:
        logger.error(f"Error initializing data file: {e}")


def get_competitions(country: str = DEFAULT_COUNTRY) -> List[Dict[str, Any]]:
    """Fetch upcoming competitions from the WCA API for a specific country.

    Args:
        country: ISO2 country code (e.g., 'CL' for Chile)

    Returns:
        List of competition dictionaries from the WCA API
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"https://www.worldcubeassociation.org/api/v0/competitions?country_iso2={country}&start={today}"

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        competitions = response.json()
        logger.info(
            f"Successfully fetched {len(competitions)} competitions from WCA API"
        )
        return competitions
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching competitions: {e}")
        return []


def load_previous_competitions() -> List[Dict[str, Any]]:
    """Load previous competitions from prev_comps.json."""
    try:
        with open(PREV_COMPS_FILE, "r") as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error reading {PREV_COMPS_FILE}: {e}")
        initialize_data_file()
        return []


def clean_old_competitions() -> int:
    """
    Remove competitions from prev_comps.json that have already ended.

    Returns:
        Number of competitions removed
    """
    today = datetime.datetime.now().date()
    comps = load_previous_competitions()

    # Filter competitions with end_date on or after today
    new_comps = [
        comp
        for comp in comps
        if datetime.datetime.strptime(comp["end_date"], "%Y-%m-%d").date() >= today
    ]

    removed_count = len(comps) - len(new_comps)

    if removed_count > 0:
        with open(PREV_COMPS_FILE, "w") as file:
            json.dump(new_comps, file, indent=4)
        logger.info(f"Removed {removed_count} completed competitions from storage")
    else:
        logger.info("No completed competitions to remove")

    return removed_count


def save_competitions(competitions: List[Dict[str, Any]]) -> bool:
    """Save current competitions to prev_comps.json only if there are changes.

    Returns:
        True if changes were saved, False otherwise
    """
    previous_comps = load_previous_competitions()

    # Compare by IDs instead of full objects
    prev_ids = {comp["id"] for comp in previous_comps}
    current_ids = {comp["id"] for comp in competitions}

    if prev_ids != current_ids:
        with open(PREV_COMPS_FILE, "w") as file:
            json.dump(competitions, file, indent=4)
        logger.info(f"Updated {PREV_COMPS_FILE} with {len(competitions)} competitions")
        return True
    else:
        logger.info(f"No changes in competitions, {PREV_COMPS_FILE} remains unchanged")
        return False


def detect_new_competitions(
    current_comps: List[Dict[str, Any]], previous_comps: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Compare current competitions with stored ones and return new ones."""
    previous_ids = {comp["id"] for comp in previous_comps}
    new_comps = [comp for comp in current_comps if comp["id"] not in previous_ids]
    return new_comps


def get_competition_status(comp: Dict[str, Any]) -> str:
    """Determine if a competition is upcoming or ongoing."""
    today = datetime.datetime.now().date()
    start_date = datetime.datetime.strptime(comp["start_date"], "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime(comp["end_date"], "%Y-%m-%d").date()

    if today < start_date:
        return "upcoming"
    elif start_date <= today <= end_date:
        return "ongoing"
    else:
        return "past"


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
        start_date = comp["start_date"]
        end_date = comp["end_date"]

        # Format dates for display
        start_date_fmt = datetime.datetime.strptime(start_date, "%Y-%m-%d").strftime(
            "%d/%m/%Y"
        )
        end_date_fmt = datetime.datetime.strptime(end_date, "%Y-%m-%d").strftime(
            "%d/%m/%Y"
        )

        # Handle multi-day competitions
        if start_date == end_date:
            date_text = f"📅 **Fecha:** {start_date_fmt}"
        else:
            days = (
                datetime.datetime.strptime(end_date, "%Y-%m-%d")
                - datetime.datetime.strptime(start_date, "%Y-%m-%d")
            ).days + 1
            date_text = (
                f"📅 **Fechas:** {start_date_fmt} → {end_date_fmt} ({days} días)"
            )

        # Get competition status and set appropriate color
        status = get_competition_status(comp)
        color = (
            EMBED_COLORS["new"]
            if is_new
            else EMBED_COLORS.get(status, EMBED_COLORS["upcoming"])
        )

        # Create status indicator
        status_emoji = "✨ NUEVO: " if is_new else ""
        if status == "ongoing":
            status_emoji += "🔴 EN CURSO: "

        # Get venue if available
        venue_info = ""
        if comp.get("venue_name") and comp.get("venue_address"):
            venue_info = f"🏢 **Sede:** {comp['venue_name']}\n📌 **Dirección:** {comp['venue_address']}\n"

        # Get registration status
        reg_info = ""
        if comp.get("registration_open") and comp.get("registration_close"):
            reg_open = datetime.datetime.strptime(
                comp["registration_open"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).strftime("%d/%m/%Y")
            reg_close = datetime.datetime.strptime(
                comp["registration_close"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).strftime("%d/%m/%Y")
            reg_info = f"📝 **Registro:** {reg_open} → {reg_close}\n"

        # Get event categories
        event_ids = comp.get("event_ids", [])
        event_names = [EVENTS.get(event_id, event_id) for event_id in event_ids]
        events_text = (
            ", ".join(event_names) if event_names else "No hay eventos disponibles"
        )

        # Create embed
        embed = {
            "title": f"{status_emoji}{comp['name']}",
            "description": (
                f"🌎 **Ciudad:** {comp.get('city', 'No disponible')}\n"
                f"{date_text}\n"
                f"{venue_info}"
                f"{reg_info}"
                f"🎯 **Eventos:** {events_text}"
            ),
            "url": comp["url"],
            "color": color,
            "footer": {"text": f"WCA Competition ID: {comp['id']}"},
        }

        # Add thumbnail if available
        if comp.get("country"):
            country_code = comp.get("country").get("iso2", "").lower()
            if country_code:
                embed["thumbnail"] = {
                    "url": f"https://flagcdn.com/w80/{country_code}.png"
                }

        embeds.append(embed)

    return embeds


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

    embeds = create_discord_embeds(competitions, is_new)

    # Prepare message content based on competition type
    if is_new:
        content = f"🎉 **¡{len(competitions)} nuevo{'s' if len(competitions) > 1 else ''} torneo{'s' if len(competitions) > 1 else ''}!**"
    else:
        content = f"📋 **Recordatorio: {len(competitions)} torneo{'s' if len(competitions) > 1 else ''} próximamente**"

    # Discord has a limit of 10 embeds per webhook message
    # Split into batches if needed
    batch_size = 10
    for i in range(0, len(embeds), batch_size):
        batch_embeds = embeds[i : i + batch_size]

        # Adjust content for batched messages
        batch_content = content
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


def main() -> None:
    """Main function to run the WCA competition tracker."""
    logger.info("Starting WCA competition tracking")

    # Ensure data file exists
    initialize_data_file()

    # Clean out competitions that have already ended - always do this
    removed_count = clean_old_competitions()
    logger.info(f"Removed {removed_count} old competitions from storage")

    logger.info(f"Fetching competitions from WCA API for country: {DEFAULT_COUNTRY}")
    current_comps = get_competitions()

    if not current_comps:
        logger.warning("No upcoming competitions found")
        # Even if there are no competitions, we've already cleaned the old ones
        return

    # Load previous competitions (after cleaning)
    previous_comps = load_previous_competitions()

    logger.info(
        f"Comparing {len(current_comps)} current competitions with {len(previous_comps)} stored competitions"
    )

    # Detect new competitions
    new_comps = detect_new_competitions(current_comps, previous_comps)

    # Process new competitions if any
    if new_comps:
        logger.info(f"Detected {len(new_comps)} new competitions")
        send_discord_notification(new_comps, is_new=True)
        # Save updated competitions list
        save_competitions(current_comps)
    else:
        logger.info("No new competitions detected")

    logger.info("WCA competition tracking completed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
