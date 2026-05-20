"""Main entry point for WCA competition tracking."""

import logging
import config
import database
import wca_api
import detection
import notifications

logger = logging.getLogger(__name__)


def main() -> None:
    """Main function to run the WCA competition tracker."""
    config.bootstrap()
    logger.info("Starting WCA competition tracking")
    database.initialize_database()
    database.clean_old_competitions()
    database.clean_old_registration_tracking()
    database.clean_old_spots_tracking()

    current_comps = wca_api.get_competitions()
    if not current_comps:
        logger.warning("No upcoming competitions found")
        return

    previous_comps = database.load_previous_competitions()
    new_comps = detection.detect_new_competitions(current_comps, previous_comps)
    if new_comps:
        notifications.send_discord_notification(new_comps, is_new=True)
        notifications.send_telegram_notification(new_comps, is_new=True)
        database.save_competitions(current_comps)

    tracking = database.load_registration_tracking()
    upcoming_reg = detection.detect_registration_opening_soon(current_comps, tracking)
    for comp in upcoming_reg:
        if notifications.send_registration_upcoming_notification(comp):
            database.mark_registration_upcoming(comp["id"], tracking)

    just_opened = detection.detect_registration_just_opened(current_comps, tracking)
    for comp in just_opened:
        if notifications.send_registration_open_notification(comp):
            database.mark_registration_open(comp["id"], tracking)

    spots_tracking = database.load_spots_tracking()
    limited_spots = detection.detect_limited_spots(current_comps, spots_tracking)
    for comp in limited_spots:
        if notifications.send_limited_spots_notification(comp):
            database.mark_spots_notified(comp["id"], spots_tracking)

    database.save_spots_tracking(spots_tracking)
    logger.info("WCA competition tracking completed")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Unhandled error: {e}", exc_info=True)
