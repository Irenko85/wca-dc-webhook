import os
import requests
import datetime
import json
from dotenv import load_dotenv

# 🔹 Cargar variables desde el archivo .env
load_dotenv()

# 🔹 Obtener el Webhook de Discord desde las variables de entorno
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 🔹 Archivo donde se guardan las competencias previas (ahora en el repo)
PREV_COMPS_FILE = "prev_comps.json"

# 🔹 Verificar si `prev_comps.json` existe
if not os.path.exists(PREV_COMPS_FILE):
    print("⚠️ prev_comps.json no encontrado. Creando archivo vacío...")
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
    try:
        with open(PREV_COMPS_FILE, "r") as file:
            return json.load(file)
    except (json.JSONDecodeError, FileNotFoundError):
        print("⚠️ Error al leer prev_comps.json. Creando un archivo vacío...")
        return []


def save_competitions(competitions):
    """Guarda la lista actual de competencias en un archivo JSON si hay cambios."""
    previous_comps = load_previous_competitions()

    if previous_comps != competitions:  # Guardar solo si hay cambios
        with open(PREV_COMPS_FILE, "w") as file:
            json.dump(competitions, file, indent=4)
        print("✅ prev_comps.json actualizado correctamente.")
    else:
        print("✅ No hay cambios en las competencias, no se actualiza prev_comps.json.")


def detect_new_competitions(current_comps, previous_comps):
    """Compara las competencias actuales con las guardadas y devuelve las nuevas."""
    previous_ids = {comp["id"] for comp in previous_comps}
    new_comps = [comp for comp in current_comps if comp["id"] not in previous_ids]
    return new_comps


def send_discord_notification(new_comps):
    """Envía notificación a Discord si hay nuevas competencias."""
    if not new_comps:
        print("✅ No hay nuevas competencias. No se enviará notificación.")
        return

    data = {
        "content": "🎉 **¡Nuevos torneos!**",
        "embeds": [
            {
                "title": f"🏆 {comp['name']}",
                "description": f"📍 {comp['city']}\n📅 {comp['start_date']}",
                "url": comp["url"],
                "color": 0x002C99,
            }
            for comp in new_comps
        ],
    }

    response = requests.post(DISCORD_WEBHOOK_URL, json=data)
    if response.status_code == 204:
        print("✅ Notificación enviada a Discord.")
    else:
        print(f"⚠️ Error enviando embed a Discord: {response.status_code}")


if __name__ == "__main__":
    current_comps = get_competitions()
    previous_comps = load_previous_competitions()

    new_comps = detect_new_competitions(current_comps, previous_comps)

    if new_comps:
        print(
            f"🎉 Se detectaron {len(new_comps)} nuevas competencias. Enviando notificación..."
        )
        send_discord_notification(new_comps)
        save_competitions(current_comps)  # Guardar solo si hay cambios
    else:
        print("✅ No hay competencias nuevas.")
