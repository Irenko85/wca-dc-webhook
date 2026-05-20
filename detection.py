import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import REGISTRATION_UPCOMING_WINDOW, SPOTS_WARNING_THRESHOLD
from wca_api import scrape_registered_competitors

logger = logging.getLogger(__name__)


def detect_new_competitions(
    current_comps: List[Dict[str, Any]], previous_comps: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Compare current competitions with stored ones and return new ones."""
    previous_ids = {comp["id"] for comp in previous_comps}
    new_comps = [comp for comp in current_comps if comp["id"] not in previous_ids]
    return new_comps


def detect_registration_opening_soon(
    competitions: List[Dict[str, Any]], tracking: Dict[str, Dict[str, bool]]
) -> List[Dict[str, Any]]:
    """Detect competitions whose registration is opening soon (within the next hour).

    Args:
        competitions: List of competition dictionaries
        tracking: Registration tracking data

    Returns:
        List of competitions with registration opening soon that haven't been notified
    """
    now = datetime.now(timezone.utc)
    opening_soon = []

    for comp in competitions:
        comp_id = comp["id"]

        # Skip if already notified about upcoming registration
        if tracking.get(comp_id, {}).get("notified_upcoming", False):
            continue

        # Skip if competition has already started
        start_date = datetime.strptime(comp["start_date"], "%Y-%m-%d").date()
        if start_date <= datetime.now().date():
            continue

        # Check if registration_open exists and is in the future
        if not comp.get("registration_open"):
            continue

        try:
            reg_open = datetime.strptime(
                comp["registration_open"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=timezone.utc)

            # Check if registration opens within the next REGISTRATION_UPCOMING_WINDOW minutes
            time_until_open = (reg_open - now).total_seconds() / 60

            if 0 < time_until_open <= REGISTRATION_UPCOMING_WINDOW:
                opening_soon.append(comp)
                logger.info(
                    f"Registration for {comp['name']} opens in {int(time_until_open)} minutes"
                )

        except (ValueError, KeyError) as e:
            logger.warning(f"Error parsing registration_open for {comp_id}: {e}")
            continue

    return opening_soon


def detect_registration_just_opened(
    competitions: List[Dict[str, Any]], tracking: Dict[str, Dict[str, bool]]
) -> List[Dict[str, Any]]:
    """Detect competitions whose registration just opened (within the last hour).

    Args:
        competitions: List of competition dictionaries
        tracking: Registration tracking data

    Returns:
        List of competitions with registration just opened that haven't been notified
    """
    now = datetime.now(timezone.utc)
    just_opened = []

    for comp in competitions:
        comp_id = comp["id"]

        # Skip if already notified about registration being open
        if tracking.get(comp_id, {}).get("notified_open", False):
            continue

        # Skip if competition has already started
        start_date = datetime.strptime(comp["start_date"], "%Y-%m-%d").date()
        if start_date <= datetime.now().date():
            continue

        # Check if registration_open exists
        if not comp.get("registration_open"):
            continue

        try:
            reg_open = datetime.strptime(
                comp["registration_open"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).replace(tzinfo=timezone.utc)

            # Check if registration opened within the last hour
            time_since_open = (now - reg_open).total_seconds() / 60

            # If registration opened between 0 and 60 minutes ago
            if 0 <= time_since_open <= 60:
                just_opened.append(comp)
                logger.info(
                    f"Registration for {comp['name']} opened {int(time_since_open)} minutes ago"
                )

        except (ValueError, KeyError) as e:
            logger.warning(f"Error parsing registration_open for {comp_id}: {e}")
            continue

    return just_opened


def detect_limited_spots(
    competitions: List[Dict[str, Any]], tracking: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Detect competitions with limited spots that are almost full.

    Args:
        competitions: List of competition dictionaries
        tracking: Spots tracking data

    Returns:
        List of competitions with spots almost full that haven't been notified
    """
    almost_full = []

    for comp in competitions:
        comp_id = comp["id"]

        # Skip if already notified
        if tracking.get(comp_id, {}).get("notified", False):
            continue

        # Skip if competition has already started
        start_date = datetime.strptime(comp["start_date"], "%Y-%m-%d").date()
        if start_date <= datetime.now().date():
            continue

        # Skip if no competitor limit
        competitor_limit = comp.get("competitor_limit")
        if not competitor_limit:
            continue

        # Scrape current number of registered competitors
        comp_url = comp["url"]
        current_count = scrape_registered_competitors(comp_url)

        if current_count is None:
            continue

        # Calculate percentage filled
        percentage_filled = current_count / competitor_limit

        # Update tracking with current count
        if comp_id not in tracking:
            tracking[comp_id] = {}
        tracking[comp_id]["last_count"] = current_count
        tracking[comp_id]["limit"] = competitor_limit

        # Check if spots are almost full (>= threshold)
        if percentage_filled >= SPOTS_WARNING_THRESHOLD:
            almost_full.append({
                **comp,
                "current_count": current_count,
                "percentage_filled": percentage_filled
            })
            logger.info(
                f"Limited spots alert: {comp['name']} has {current_count}/{competitor_limit} spots filled "
                f"({percentage_filled*100:.1f}%)"
            )

    return almost_full
