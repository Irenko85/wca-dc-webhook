import os
import logging
from typing import Optional
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


def check_env_var(var_name: str) -> Optional[str]:
    """Check if an environment variable exists and log a warning if not."""
    value = os.getenv(var_name)
    if not value:
        logger.warning(
            f"{var_name} not found in environment variables! Was the main.yml updated?"
        )
    return value


# Get Discord webhook URL and Telegram credentials
DISCORD_WEBHOOK_URL = check_env_var("DISCORD_WEBHOOK_URL")
TELEGRAM_BOT_TOKEN = check_env_var("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL_ID = check_env_var("TELEGRAM_CHANNEL_ID")

# Constants
DB_FILE = os.getenv("DB_PATH", "wca_tracker.sqlite3")
DEFAULT_COUNTRY = "CL"  # Chile as default country
REQUEST_TIMEOUT = 10  # seconds
REGISTRATION_UPCOMING_WINDOW = 60  # minutes before registration opens to send "upcoming" notification
SPOTS_WARNING_THRESHOLD = 0.80  # Notify when 80% of spots are taken

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
