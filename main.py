"""Main entry point for WCA competition tracking."""

import logging

import config
from config import DEFAULT_COUNTRY

from database import (
    initialize_database,
    load_previous_competitions,
    save_competitions,
    clean_old_competitions,
    load_registration_tracking,
    save_registration_tracking,
    clean_old_registration_tracking,
    load_spots_tracking,
    save_spots_tracking,
    clean_old_spots_tracking,
)

from wca_api import get_competitions

from detection import (
    detect_new_competitions,
    detect_registration_opening_soon,
    detect_registration_just_opened,
    detect_limited_spots,
)

from notifications import (
    send_discord_notification,
    send_telegram_notification,
    send_registration_upcoming_notification,
    send_registration_open_notification,
    send_limited_spots_notification,
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Main function to run the WCA competition tracker."""
    config.bootstrap()
    logger.info("Starting WCA competition tracking")

    # Ensure data files exist
    initialize_database()

    # Clean out old data
    removed_count = clean_old_competitions()
    logger.info(f"Removed {removed_count} old competitions from storage")

    removed_tracking = clean_old_registration_tracking()
    logger.info(f"Removed {removed_tracking} old tracking entries")

    removed_spots = clean_old_spots_tracking()
    logger.info(f"Removed {removed_spots} old spots tracking entries")

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
        send_telegram_notification(new_comps, is_new=True)
        # Save updated competitions list
        save_competitions(current_comps)
    else:
        logger.info("No new competitions detected")

    # Check for registration notifications
    logger.info("Checking for registration opening notifications")
    tracking = load_registration_tracking()

    # Detect competitions with registration opening soon
    upcoming_reg = detect_registration_opening_soon(current_comps, tracking)
    if upcoming_reg:
        logger.info(
            f"Found {len(upcoming_reg)} competitions with registration opening soon"
        )
        for comp in upcoming_reg:
            if send_registration_upcoming_notification(comp):
                # Mark as notified
                if comp["id"] not in tracking:
                    tracking[comp["id"]] = {"notified_upcoming": False, "notified_open": False}
                tracking[comp["id"]]["notified_upcoming"] = True
                save_registration_tracking(tracking)
    else:
        logger.info("No competitions with registration opening soon")

    # Detect competitions with registration just opened
    just_opened_reg = detect_registration_just_opened(current_comps, tracking)
    if just_opened_reg:
        logger.info(
            f"Found {len(just_opened_reg)} competitions with registration just opened"
        )
        for comp in just_opened_reg:
            if send_registration_open_notification(comp):
                # Mark as notified
                if comp["id"] not in tracking:
                    tracking[comp["id"]] = {"notified_upcoming": False, "notified_open": False}
                tracking[comp["id"]]["notified_open"] = True
                save_registration_tracking(tracking)
    else:
        logger.info("No competitions with registration just opened")

    # Check for limited spots notifications
    logger.info("Checking for limited spots notifications")
    spots_tracking = load_spots_tracking()

    # Detect competitions with limited spots
    limited_spots = detect_limited_spots(current_comps, spots_tracking)
    if limited_spots:
        logger.info(
            f"Found {len(limited_spots)} competitions with limited spots"
        )
        for comp in limited_spots:
            if send_limited_spots_notification(comp):
                # Mark as notified
                if comp["id"] not in spots_tracking:
                    spots_tracking[comp["id"]] = {}
                spots_tracking[comp["id"]]["notified"] = True
                save_spots_tracking(spots_tracking)
    else:
        logger.info("No competitions with limited spots")

    # Save spots tracking even if no notifications sent (to update last_count)
    save_spots_tracking(spots_tracking)

    logger.info("WCA competition tracking completed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
