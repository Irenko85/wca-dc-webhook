import requests
import logging
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from config import REQUEST_TIMEOUT, DEFAULT_COUNTRY

logger = logging.getLogger(__name__)


def get_competitions(country: str = DEFAULT_COUNTRY) -> List[Dict[str, Any]]:
    """Fetch upcoming competitions from the WCA API for a specific country.

    Args:
        country: ISO2 country code (e.g., 'CL' for Chile)

    Returns:
        List of competition dictionaries from the WCA API
    """
    import datetime

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


def scrape_registered_competitors(comp_url: str) -> Optional[int]:
    """Get the number of registered competitors from competition WCIF API.

    Args:
        comp_url: Base URL of the competition (e.g., https://www.worldcubeassociation.org/competitions/CompID)

    Returns:
        Number of accepted competitors, or None if API call failed
    """
    try:
        # Extract competition ID from URL
        comp_id = comp_url.rstrip('/').split('/')[-1]

        # Use WCIF public API endpoint
        wcif_url = f"https://www.worldcubeassociation.org/api/v0/competitions/{comp_id}/wcif/public"
        response = requests.get(wcif_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        data = response.json()
        persons = data.get('persons', [])

        # Count only accepted competitors (not pending/waiting list, not staff without registration)
        accepted_count = len([
            p for p in persons
            if p.get('registration') and p['registration'].get('status') == 'accepted'
        ])

        logger.info(f"Found {accepted_count} accepted competitors for {comp_id}")
        return accepted_count

    except Exception as e:
        logger.error(f"Error getting competitor count from WCIF API for {comp_url}: {e}")
        return None
