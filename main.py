import os
import requests
import datetime
import json
from dotenv import load_dotenv

load_dotenv()

# Cargar variables desde los Secrets de GitHub
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Archivo donde se guardan las competencias previas
PREV_COMPS_FILE = "prev_comps.json"

if not os.path.exists(PREV_COMPS_FILE):
    with open(PREV_COMPS_FILE, "w") as file:
        json.dump([], file)

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
    """Obtiene las competencias desde la API de la WCA con la fecha actual."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"https://www.worldcubeassociation.org/api/v0/competitions?country_iso2={country}&start={today}"
    response = requests.get(url)

    if response.status_code == 200:
        return response.json()

    return []


def load_previous_competitions():
    """Carga la lista de competencias previas desde un archivo JSON."""
    if os.path.exists(PREV_COMPS_FILE):
        with open(PREV_COMPS_FILE, "r") as file:
            return json.load(file)
    return []


def save_competitions(competitions):
    """Guarda la lista actual de competencias en un archivo JSON."""
    with open(PREV_COMPS_FILE, "w") as file:
        json.dump(competitions, file, indent=4)


def detect_new_competitions(current_comps, previous_comps):
    """Compara las competencias actuales con las guardadas y devuelve las nuevas."""
    previous_ids = {comp["id"] for comp in previous_comps}
    new_comps = [comp for comp in current_comps if comp["id"] not in previous_ids]
    return new_comps


def create_discord_embeds(competitions):
    """Genera una lista de embeds de Discord para las nuevas competencias."""
    embeds = []

    for comp in competitions:
        start_date = comp["start_date"]
        end_date = comp["end_date"]

        # Manejo de fechas para competencias de más de 1 día
        if start_date == end_date:
            date_text = f"📅 **Fecha:** {start_date}"
        else:
            days = (
                datetime.datetime.strptime(end_date, "%Y-%m-%d")
                - datetime.datetime.strptime(start_date, "%Y-%m-%d")
            ).days + 1
            date_text = f"📅 **Fechas:** {start_date} → {end_date} ({days} días)"

        # Obtener eventos de la competencia
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
    """Envía notificación a Discord si hay nuevas competencias."""
    if not new_comps:
        return

    embeds = create_discord_embeds(new_comps)  # Generamos los embeds

    if DISCORD_WEBHOOK_URL:
        data = {
            "content": "🎉 **¡Nuevos torneos!**",
            "embeds": embeds,
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=data)
        if response.status_code == 204:
            print("✅ Notification sent to Discord.")
        else:
            print(f"⚠️ Error sending embed to Discord: {response.status_code}")


if __name__ == "__main__":
    current_comps = get_competitions()
    previous_comps = load_previous_competitions()

    new_comps = detect_new_competitions(current_comps, previous_comps)

    if new_comps:
        print("🎉 New competitions detected. Sending notification...")
        send_discord_notification(new_comps)
        save_competitions(current_comps)
    else:
        print("✅ No new competitions.")
