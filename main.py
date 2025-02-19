import os
import requests
import datetime
import json

# Cargar variables desde los Secrets de GitHub
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Archivo donde se guardan las competencias previas
PREV_COMPS_FILE = "prev_comps.json"


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

        # Si la competencia dura más de un día, lo indicamos en la fecha
        if start_date == end_date:
            date_text = f"📅 **Date:** {start_date}"
        else:
            date_text = f"📅 **Dates:** {start_date} → {end_date} ({(datetime.datetime.strptime(end_date, '%Y-%m-%d') - datetime.datetime.strptime(start_date, '%Y-%m-%d')).days + 1} days)"

        embed = {
            "title": f"🏆 {comp['name']}",
            "description": f"📍 **City:** {comp['city']}\n{date_text}",
            "url": comp["url"],
            "color": 0x002C99,  # Azul
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
