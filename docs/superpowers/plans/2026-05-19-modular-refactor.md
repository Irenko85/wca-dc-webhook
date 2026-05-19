# Modular Refactor of `main.py` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `main.py` into 5 flat modules plus a thin orchestrator, sin cambiar comportamiento ni dependencias.

**Architecture:** Un solo sentido de dependencias: `config.py` en la base, el resto de módulos lo importan, y `main.py` solo orquesta. Cada módulo expone una responsabilidad clara para evitar imports circulares y mantener importabilidad independiente. El runtime debe seguir produciendo los mismos logs, payloads y consultas a SQLite/WCA.

**Tech Stack:** Python 3.12, `sqlite3`, `requests`, `beautifulsoup4`, `python-dotenv`

---

## Contexto relevante

- `main.py:1-72` — bootstrap, logging, dotenv, constantes y env vars
- `main.py:75-456` — persistencia SQLite y tracking
- `main.py:104-392` — cliente WCA / WCIF
- `main.py:188-518` — detección de eventos/notificaciones pendientes
- `main.py:521-1107` — formateo y envío de notificaciones
- `main.py:1110-1221` — orquestación y entrypoint

## Decisiones de diseño

1. **Módulos planos en raíz** — minimiza cambios de import y evita reestructurar paquetes
2. **`config.py` como única fuente de constantes** — evita duplicación y reduce riesgo de divergencia
3. **`main.py` sin lógica de negocio** — solo inicializa y ejecuta el flujo; ≤ 60 líneas
4. **Importación unidireccional** — ningún módulo importa `main.py`; cada módulo es importable por separado

---

## Task 1: Extraer configuración y constantes

**Files:**
- Create: `config.py`
- Modify: `main.py`

- [ ] **Step 1: Crear `config.py`**

  Mover aquí desde `main.py` líneas 1-72:
  - `load_dotenv()` call
  - Setup de `logging.basicConfig`
  - `check_env_var()` función
  - Constantes: `DB_FILE`, `DEFAULT_COUNTRY`, `REQUEST_TIMEOUT`, `REGISTRATION_UPCOMING_WINDOW`, `SPOTS_WARNING_THRESHOLD`
  - Dicts: `EVENTS`, `EMBED_COLORS`
  - Env vars: `DISCORD_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`

  El archivo debe quedar exactamente con estos valores y no ejecutar ninguna lógica de red ni de DB.

- [ ] **Step 2: Actualizar `main.py`**

  Reemplazar el bloque bootstrap (líneas 1-72) por:
  ```python
  from config import (
      DISCORD_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID,
      DB_FILE, DEFAULT_COUNTRY, REGISTRATION_UPCOMING_WINDOW,
      SPOTS_WARNING_THRESHOLD, EVENTS, EMBED_COLORS,
  )
  ```
  Eliminar las constantes duplicadas del resto del archivo.

- [ ] **Step 3: Verificación**

  ```
  python -c "import config"
  python -c "import main"
  ```
  Expected: sin traceback.

- [ ] **Step 4: Commit**

  ```bash
  git add config.py main.py
  git commit -m "refactor: extract shared config"
  ```

---

## Task 2: Extraer capa de base de datos

**Files:**
- Create: `database.py`
- Modify: `main.py`

- [ ] **Step 1: Crear `database.py`**

  Mover desde `main.py` todas las funciones de persistencia SQLite:
  - `initialize_database()`
  - `load_previous_competitions()` → `list[dict]`
  - `save_competitions(competitions)` → `bool`
  - `clean_old_competitions()`
  - `load_registration_tracking()` → `dict`
  - `save_registration_tracking(tracking_data)`
  - `clean_old_registration_tracking(competitions)`
  - `load_spots_tracking()` → `dict`
  - `save_spots_tracking(tracking_data)`
  - `clean_old_spots_tracking(competitions)`

  Imports necesarios:
  ```python
  import sqlite3
  import json
  import logging
  from datetime import datetime, timezone
  from config import DB_FILE
  ```

  Mantener exactamente las mismas tablas, columnas, consultas y logging.

- [ ] **Step 2: Actualizar `main.py`**

  Reemplazar las funciones locales por:
  ```python
  from database import (
      initialize_database, load_previous_competitions, save_competitions,
      clean_old_competitions, load_registration_tracking,
      save_registration_tracking, clean_old_registration_tracking,
      load_spots_tracking, save_spots_tracking, clean_old_spots_tracking,
  )
  ```

- [ ] **Step 3: Verificación**

  ```
  python -c "import database"
  python -c "import main"
  ```
  Expected: sin traceback.

- [ ] **Step 4: Commit**

  ```bash
  git add database.py main.py
  git commit -m "refactor: move database helpers"
  ```

---

## Task 3: Extraer cliente WCA

**Files:**
- Create: `wca_api.py`
- Modify: `main.py`

- [ ] **Step 1: Crear `wca_api.py`**

  Mover desde `main.py`:
  - `get_competitions(country=DEFAULT_COUNTRY)` → `list[dict]`
  - `scrape_registered_competitors(comp_url)` → `int`

  Imports necesarios:
  ```python
  import requests
  import logging
  from bs4 import BeautifulSoup
  from config import REQUEST_TIMEOUT, DEFAULT_COUNTRY
  ```

  Mantener URLs, manejo de errores HTTP, parsing y conteo de competidores idénticos.

- [ ] **Step 2: Actualizar `main.py`**

  ```python
  from wca_api import get_competitions, scrape_registered_competitors
  ```

- [ ] **Step 3: Verificación**

  ```
  python -c "import wca_api"
  python -c "import main"
  ```
  Expected: sin traceback.

- [ ] **Step 4: Commit**

  ```bash
  git add wca_api.py main.py
  git commit -m "refactor: extract wca api client"
  ```

---

## Task 4: Extraer lógica de detección

**Files:**
- Create: `detection.py`
- Modify: `main.py`

- [ ] **Step 1: Crear `detection.py`**

  Mover desde `main.py`:
  - `detect_new_competitions(current, previous)` → `list[dict]`
  - `detect_registration_opening_soon(competitions, tracking)` → `list[dict]`
  - `detect_registration_just_opened(competitions, tracking)` → `list[dict]`
  - `detect_limited_spots(competitions, tracking)` → `list[dict]`

  Imports necesarios:
  ```python
  import logging
  from datetime import datetime, timezone
  from config import REGISTRATION_UPCOMING_WINDOW, SPOTS_WARNING_THRESHOLD
  from wca_api import scrape_registered_competitors
  ```

  Sin I/O de DB ni red directa (excepto el call delegado a `scrape_registered_competitors`).
  Mantener filtros, parsing de fechas y logging idénticos.

- [ ] **Step 2: Actualizar `main.py`**

  ```python
  from detection import (
      detect_new_competitions, detect_registration_opening_soon,
      detect_registration_just_opened, detect_limited_spots,
  )
  ```

- [ ] **Step 3: Verificación**

  ```
  python -c "import detection"
  python -c "import main"
  ```
  Expected: sin traceback.

- [ ] **Step 4: Commit**

  ```bash
  git add detection.py main.py
  git commit -m "refactor: split detection logic"
  ```

---

## Task 5: Extraer notificaciones y formateo

**Files:**
- Create: `notifications.py`
- Modify: `main.py`

- [ ] **Step 1: Crear `notifications.py`**

  Mover desde `main.py`:
  - `format_competition_info(comp)` → `dict`
  - `get_competition_status(comp)` → `str`
  - `sort_competitions_by_date(competitions, reverse=False)` → `list`
  - `create_notification_header(competitions, is_new)` → `tuple[str, str]`
  - `create_discord_embeds(competitions, is_new)` → `list`
  - `create_telegram_message(competition, header)` → `str`
  - `send_discord_notification(competitions, is_new)`
  - `send_telegram_notification(competitions, is_new)`
  - `send_registration_upcoming_notification(comp)`
  - `send_registration_open_notification(comp)`
  - `send_limited_spots_notification(comp)`

  Imports necesarios:
  ```python
  import requests
  import logging
  from datetime import datetime, timezone
  from config import (
      DISCORD_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID,
      REQUEST_TIMEOUT, EVENTS, EMBED_COLORS,
  )
  ```

  Mantener exactamente los mismos textos, colores, payloads y lógica de batching de Discord.

- [ ] **Step 2: Actualizar `main.py`**

  ```python
  from notifications import (
      send_discord_notification, send_telegram_notification,
      send_registration_upcoming_notification,
      send_registration_open_notification,
      send_limited_spots_notification,
  )
  ```

- [ ] **Step 3: Verificación**

  ```
  python -c "import notifications"
  python -c "import main"
  ```
  Expected: sin traceback.

- [ ] **Step 4: Commit**

  ```bash
  git add notifications.py main.py
  git commit -m "refactor: move notification helpers"
  ```

---

## Task 6: Reducir `main.py` a orquestador

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Limpiar `main.py`**

  El archivo debe quedar solo con imports y la función `main()`:

  ```python
  import logging
  from config import DEFAULT_COUNTRY  # y lo que sea necesario
  from database import (
      initialize_database, load_previous_competitions, save_competitions,
      clean_old_competitions, load_registration_tracking,
      save_registration_tracking, clean_old_registration_tracking,
      load_spots_tracking, save_spots_tracking, clean_old_spots_tracking,
  )
  from wca_api import get_competitions
  from detection import (
      detect_new_competitions, detect_registration_opening_soon,
      detect_registration_just_opened, detect_limited_spots,
  )
  from notifications import (
      send_discord_notification, send_telegram_notification,
      send_registration_upcoming_notification,
      send_registration_open_notification,
      send_limited_spots_notification,
  )

  def main():
      initialize_database()
      clean_old_competitions()
      # ... flujo orquestado con las funciones importadas ...

  if __name__ == "__main__":
      main()
  ```

  Flujo exacto a mantener:
  1. `initialize_database()`
  2. `clean_old_competitions()` / `clean_old_registration_tracking()` / `clean_old_spots_tracking()`
  3. `get_competitions()`
  4. `load_previous_competitions()` → `detect_new_competitions()`
  5. `send_discord_notification()` / `send_telegram_notification()` si hay nuevas
  6. `save_competitions()`
  7. `load_registration_tracking()` → `detect_registration_opening_soon()` → notificar
  8. `detect_registration_just_opened()` → notificar
  9. `save_registration_tracking()`
  10. `load_spots_tracking()` → `detect_limited_spots()` → notificar
  11. `save_spots_tracking()`

  Verificar que el archivo quede en ≤ 60 líneas.

- [ ] **Step 2: Verificación final**

  ```
  python -c "import config, database, wca_api, detection, notifications, main"
  ```
  Expected: todos importan sin traceback ni side effects.

- [ ] **Step 3: Commit**

  ```bash
  git add main.py
  git commit -m "refactor: slim main orchestrator"
  ```

---

## Verificación global

```
python -c "import config, database, wca_api, detection, notifications, main"
```

- Sin traceback = éxito
- NO ejecutar `python main.py` directamente (hace llamadas live a WCA/Discord/Telegram)

## Fuera de alcance

- Cambios de comportamiento o lógica de negocio
- Nuevas dependencias
- Cambios en `Dockerfile` o `docker-compose.yml`
- Tests automatizados nuevos
- Migración a paquete `src/` o subpaquetes
