import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

from config import DB_FILE

logger = logging.getLogger(__name__)


def initialize_database() -> None:
    """Inicializa la base de datos SQLite con las tablas necesarias."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS competitions (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS registration_tracking (
                comp_id TEXT PRIMARY KEY,
                notified_upcoming INTEGER NOT NULL DEFAULT 0,
                notified_open INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS spots_tracking (
                comp_id TEXT PRIMARY KEY,
                notified INTEGER NOT NULL DEFAULT 0,
                last_count INTEGER,
                spot_limit INTEGER
            );
        """)


def load_previous_competitions() -> List[Dict[str, Any]]:
    """Carga todas las competencias almacenadas desde SQLite."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM competitions")
            rows = cursor.fetchall()
        return [json.loads(row[0]) for row in rows]
    except sqlite3.Error as e:
        logger.error(f"Error cargando competencias desde SQLite: {e}")
        return []


def save_competitions(competitions: List[Dict[str, Any]]) -> bool:
    """Persiste competencias en SQLite. Retorna True si hay competencias nuevas."""
    previous = load_previous_competitions()
    prev_ids = {comp["id"] for comp in previous}
    current_ids = {comp["id"] for comp in competitions}
    has_new = bool(current_ids - prev_ids)

    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            for comp in competitions:
                cursor.execute("""
                    INSERT INTO competitions (id, data, start_date, end_date, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        data = excluded.data,
                        start_date = excluded.start_date,
                        end_date = excluded.end_date,
                        updated_at = CURRENT_TIMESTAMP
                """, (comp["id"], json.dumps(comp), comp["start_date"], comp["end_date"]))

            # Eliminar comps que ya no están en la lista actual
            removed_ids = prev_ids - current_ids
            for comp_id in removed_ids:
                cursor.execute("DELETE FROM competitions WHERE id = ?", (comp_id,))
    except sqlite3.Error as e:
        logger.error(f"Error guardando competencias en SQLite: {e}")
        return False

    return has_new


def clean_old_competitions() -> int:
    """Elimina competencias cuya end_date ya pasó."""
    today = datetime.now().date().isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM competitions WHERE end_date < ?", (today,))
        removed_count = cursor.rowcount
    if removed_count > 0:
        logger.info(f"Removed {removed_count} completed competitions from storage")
    else:
        logger.info("No completed competitions to remove")
    return removed_count


def load_registration_tracking() -> Dict[str, Dict[str, bool]]:
    """Carga el tracking de notificaciones de registro desde SQLite."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT comp_id, notified_upcoming, notified_open FROM registration_tracking")
            rows = cursor.fetchall()
        return {
            row[0]: {"notified_upcoming": bool(row[1]), "notified_open": bool(row[2])}
            for row in rows
        }
    except sqlite3.Error as e:
        logger.error(f"Error cargando registration_tracking desde SQLite: {e}")
        return {}


def save_registration_tracking(tracking_data: Dict[str, Dict[str, bool]]) -> None:
    """Persiste el tracking de notificaciones de registro en SQLite."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        for comp_id, flags in tracking_data.items():
            cursor.execute("""
                INSERT INTO registration_tracking (comp_id, notified_upcoming, notified_open)
                VALUES (?, ?, ?)
                ON CONFLICT(comp_id) DO UPDATE SET
                    notified_upcoming = excluded.notified_upcoming,
                    notified_open = excluded.notified_open
            """, (
                comp_id,
                int(flags.get("notified_upcoming", False)),
                int(flags.get("notified_open", False))
            ))
    logger.info("Updated registration tracking in database")


def clean_old_registration_tracking() -> int:
    """Elimina tracking de competencias que ya han comenzado o no existen."""
    today = datetime.now().date().isoformat()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM registration_tracking
                WHERE comp_id NOT IN (
                    SELECT id FROM competitions WHERE start_date > ?
                )
            """, (today,))
            removed_count = cursor.rowcount
    except sqlite3.Error as e:
        logger.error(f"Error limpiando registration_tracking: {e}")
        return 0
    if removed_count > 0:
        logger.info(f"Removed {removed_count} old entries from registration tracking")
    else:
        logger.info("No old registration tracking entries to remove")
    return removed_count


def load_spots_tracking() -> Dict[str, Dict[str, Any]]:
    """Carga el tracking de cupos disponibles desde SQLite."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT comp_id, notified, last_count, spot_limit FROM spots_tracking")
            rows = cursor.fetchall()
        result = {}
        for row in rows:
            result[row[0]] = {
                "notified": bool(row[1]),
                "last_count": row[2],
                "limit": row[3]
            }
        return result
    except sqlite3.Error as e:
        logger.error(f"Error cargando spots_tracking desde SQLite: {e}")
        return {}


def save_spots_tracking(tracking_data: Dict[str, Dict[str, Any]]) -> None:
    """Persiste el tracking de cupos en SQLite."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        for comp_id, data in tracking_data.items():
            cursor.execute("""
                INSERT INTO spots_tracking (comp_id, notified, last_count, spot_limit)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(comp_id) DO UPDATE SET
                    notified = excluded.notified,
                    last_count = excluded.last_count,
                    spot_limit = excluded.spot_limit
            """, (
                comp_id,
                int(data.get("notified", False)),
                data.get("last_count"),
                data.get("limit")
            ))
    logger.info("Updated spots tracking in database")


def clean_old_spots_tracking() -> int:
    """Elimina tracking de cupos de competencias que ya han comenzado o no existen."""
    today = datetime.now().date().isoformat()
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM spots_tracking
                WHERE comp_id NOT IN (
                    SELECT id FROM competitions WHERE start_date > ?
                )
            """, (today,))
            removed_count = cursor.rowcount
    except sqlite3.Error as e:
        logger.error(f"Error limpiando spots_tracking: {e}")
        return 0
    if removed_count > 0:
        logger.info(f"Removed {removed_count} old entries from spots tracking")
    else:
        logger.info("No old spots tracking entries to remove")
    return removed_count
