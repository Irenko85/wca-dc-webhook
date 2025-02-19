import os
import requests
import datetime
import json
from dotenv import load_dotenv

# 🔹 Load environment variables
load_dotenv()

# 🔹 Get Discord webhook URL from environment variables
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 🔹 File where previous competitions are stored
PREV_COMPS_FILE = "prev_comps.json"

# 🔹 Ensure `prev_comps.json` exists
if not os.path.exists(PREV_COMPS_FILE):
    print("⚠️ prev_comps.json not found. Creating an empty file...")
    with open(PREV_COMPS_FILE, "w") as file:
        json.dump([], file)

# 🔹 Event dictionary for competition categories
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
}


def get_competitions(country="CL"):
    """Fetch competitions from WCA API with today's date."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"https://www.worldcubeassociation.org/api/v0/competitions?country_iso2={country}&start={today}"
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()

    return []


def load_previous_competitions():
    """Load previous competitions from `prev_comps.json`."""
    try:
        with open(PREV_COMPS_FILE, "r") as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        print("⚠️ Error reading prev_comps.json. Creating a new empty file...")
        return []


def save_competitions(competitions):
    """Save current competitions to `prev_comps.json` only if there are changes."""
    previous_comps = load_previous_competitions()

    if previous_comps != competitions:  # Save only if there are changes
        with open(PREV_COMPS_FILE, "w") as file:
            json.dump(competitions, file, indent=4)
        print("✅ prev_comps.json successfully updated.")
    else:
        print("✅ No changes in competitions, prev_comps.json remains unchanged.")


def detect_new_competitions(current_comps, previous_comps):
    """Compare current competitions with stored ones and return new ones."""
    previous_ids = {comp["id"] for comp in previous_comps}
    new_comps = [comp for comp in current_comps if comp["id"] not in previous_ids]
    return new_comps


def create_discord_embeds(competitions):
    """Generate Discord embeds for new competitions."""
    embeds = []

    for comp in competitions:
        start_date = comp["start_date"]
        end_date = comp["end_date"]

        # Handle multi-day competitions
        if start_date == end_date:
            date_text = f"📅 **Fecha:** {start_date}"
        else:
            days = (
                datetime.datetime.strptime(end_date, "%Y-%m-%d")
                - datetime.datetime.strptime(start_date, "%Y-%m-%d")
            ).days + 1
            date_text = f"📅 **Fechas:** {start_date} → {end_date} ({days} días)"

        # Get event categories
        event_ids = comp.get("event_ids", [])
        event_names = [EVENTS.get(event_id, event_id) for event_id in event_ids]
        events_text = (
            ", ".join(event_names) if event_names else "No hay eventos disponibles"
        )

        embed = {
            "title": f"🏆 {comp['name']}",
            "description": f"📍 **Ciudad:** {comp['city']}\n{date_text}\n🎯 **Eventos:** {events_text}",
            "url": comp["url"],
            "color": 0x002C99,
        }

        embeds.append(embed)

    return embeds


def send_discord_notification(new_comps):
    """Send a notification to Discord if new competitions are found."""
    if not new_comps:
        print("✅ No new competitions found. No notification sent.")
        return

    embeds = create_discord_embeds(new_comps)  # Generate embeds

    if DISCORD_WEBHOOK_URL:
        data = {
            "content": "🎉 **¡Nuevos torneos!**",
            "embeds": embeds,
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        if response.status_code == 204:
            print("✅ Notification successfully sent to Discord.")
        else:
            print(f"⚠️ Error sending embed to Discord: {response.status_code}")


if __name__ == "__main__":
    print("🔍 Fetching competitions from WCA API...")
    current_comps = get_competitions()
    previous_comps = load_previous_competitions()

    print("🔍 Comparing with prev_comps.json...")
    print(f"📌 Previous competitions: {len(previous_comps)}")
    print(f"📌 Current competitions: {len(current_comps)}")

    new_comps = detect_new_competitions(current_comps, previous_comps)

    if new_comps:
        print(f"🎉 {len(new_comps)} new competitions detected. Sending notification...")
        send_discord_notification(new_comps)
        save_competitions(current_comps)  # Save only if there are changes
    else:
        print("✅ No new competitions detected.")
