# Docker Hosting Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar la persistencia de 3 archivos JSON a SQLite y hospedar el script en un servidor propio con Docker Compose + supercronic, eliminando la dependencia de GitHub Actions.

**Architecture:** Se reemplazan las funciones de lectura/escritura de JSON por operaciones SQLite usando el módulo built-in `sqlite3`. El script corre dentro de un contenedor Docker administrado por supercronic (cron para contenedores), con el archivo `.sqlite3` persistido en un bind mount local `./data/`. El workflow de GitHub Actions se elimina.

**Tech Stack:** Python 3.12-slim, SQLite3 (built-in), supercronic 0.2.33, Docker Compose v2

---

## File Map

| Acción | Archivo | Qué cambia |
|--------|---------|------------|
| Modify | `main.py` | Reemplazar funciones JSON por funciones SQLite |
| Modify | `.gitignore` | Agregar `data/` y `.env` |
| Create | `Dockerfile` | Imagen Python + supercronic |
| Create | `docker-compose.yml` | Servicio + bind mount + env_file |
| Create | `crontab` | Schedule `0 * * * *` para supercronic |
| Create | `.env.example` | Template de variables de entorno |
| Delete | `.github/workflows/main.yml` | Eliminar workflow de GitHub Actions |

---

## Task 1: Crear branch de trabajo

**Files:**
- (ningún archivo — solo git)

- [ ] **Step 1: Crear y cambiar a la branch de trabajo**

```bash
git checkout -b feature/docker-hosting-migration
```

Expected: `Switched to a new branch 'feature/docker-hosting-migration'`

---

## Task 2: Actualizar .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Agregar entradas al .gitignore**

Abrir `.gitignore` y agregar al final:

```
# Entorno local
.env

# Base de datos local (persiste en el servidor)
data/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add .env and data/ to gitignore"
```

---

## Task 3: Migrar persistencia de JSON a SQLite en main.py

Esta es la tarea central. Se reemplazan las ~10 funciones de persistencia JSON por equivalentes SQLite. **La lógica de negocio NO cambia.** Solo cambia la capa de persistencia.

**Files:**
- Modify: `main.py`

### 3a — Agregar constante DB_FILE y función initialize_database()

- [ ] **Step 1: Agregar constante DB_FILE después de las constantes de archivos JSON (línea ~41)**

Localizar las líneas:
```python
PREV_COMPS_FILE = Path("prev_comps.json")
REGISTRATION_TRACKING_FILE = Path("registration_tracking.json")
SPOTS_TRACKING_FILE = Path("spots_tracking.json")
```

Agregar DEBAJO de esas líneas:
```python
import sqlite3
DB_FILE = os.getenv("DB_PATH", "wca_tracker.sqlite3")
```

- [ ] **Step 2: Reemplazar las funciones initialize_data_file(), initialize_registration_tracking_file() e initialize_spots_tracking_file() por una sola función initialize_database()**

Eliminar las tres funciones existentes y reemplazarlas por:

```python
def initialize_database() -> None:
    """Inicializa la base de datos SQLite con las tablas necesarias."""
    conn = sqlite3.connect(DB_FILE)
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
    conn.commit()
    conn.close()
```

### 3b — Reemplazar funciones de competitions (prev_comps.json)

- [ ] **Step 3: Reemplazar load_previous_competitions()**

Eliminar la función `load_previous_competitions()` existente y reemplazar por:

```python
def load_previous_competitions() -> List[Dict[str, Any]]:
    """Carga todas las competencias almacenadas desde SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM competitions")
    rows = cursor.fetchall()
    conn.close()
    return [json.loads(row[0]) for row in rows]
```

- [ ] **Step 4: Reemplazar save_competitions()**

Eliminar la función `save_competitions()` existente y reemplazar por:

```python
def save_competitions(competitions: List[Dict[str, Any]]) -> bool:
    """Guarda la lista de competencias en SQLite. Retorna True si hubo cambios."""
    previous = load_previous_competitions()
    prev_ids = {comp["id"] for comp in previous}
    current_ids = {comp["id"] for comp in competitions}

    if prev_ids == current_ids:
        return False

    conn = sqlite3.connect(DB_FILE)
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
    if current_ids != prev_ids:
        removed_ids = prev_ids - current_ids
        for comp_id in removed_ids:
            cursor.execute("DELETE FROM competitions WHERE id = ?", (comp_id,))

    conn.commit()
    conn.close()
    return True
```

- [ ] **Step 5: Reemplazar clean_old_competitions()**

Eliminar la función `clean_old_competitions()` existente y reemplazar por:

```python
def clean_old_competitions() -> None:
    """Elimina competencias cuya end_date ya pasó."""
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM competitions WHERE end_date < ?", (today,))
    conn.commit()
    conn.close()
```

### 3c — Reemplazar funciones de registration_tracking

- [ ] **Step 6: Reemplazar load_registration_tracking()**

Eliminar la función `load_registration_tracking()` existente y reemplazar por:

```python
def load_registration_tracking() -> Dict[str, Dict[str, bool]]:
    """Carga el tracking de notificaciones de registro desde SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT comp_id, notified_upcoming, notified_open FROM registration_tracking")
    rows = cursor.fetchall()
    conn.close()
    return {
        row[0]: {"notified_upcoming": bool(row[1]), "notified_open": bool(row[2])}
        for row in rows
    }
```

- [ ] **Step 7: Reemplazar save_registration_tracking()**

Eliminar la función `save_registration_tracking()` existente y reemplazar por:

```python
def save_registration_tracking(tracking_data: Dict[str, Dict[str, bool]]) -> None:
    """Persiste el tracking de notificaciones de registro en SQLite."""
    conn = sqlite3.connect(DB_FILE)
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
    conn.commit()
    conn.close()
```

- [ ] **Step 8: Reemplazar clean_old_registration_tracking()**

Eliminar la función `clean_old_registration_tracking()` existente y reemplazar por:

```python
def clean_old_registration_tracking() -> None:
    """Elimina tracking de comps que ya no están en la tabla competitions."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM registration_tracking
        WHERE comp_id NOT IN (SELECT id FROM competitions)
    """)
    conn.commit()
    conn.close()
```

### 3d — Reemplazar funciones de spots_tracking

- [ ] **Step 9: Reemplazar load_spots_tracking()**

Eliminar la función `load_spots_tracking()` existente y reemplazar por:

```python
def load_spots_tracking() -> Dict[str, Dict[str, Any]]:
    """Carga el tracking de cupos disponibles desde SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT comp_id, notified, last_count, spot_limit FROM spots_tracking")
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for row in rows:
        result[row[0]] = {
            "notified": bool(row[1]),
            "last_count": row[2],
            "limit": row[3]
        }
    return result
```

- [ ] **Step 10: Reemplazar save_spots_tracking()**

Eliminar la función `save_spots_tracking()` existente y reemplazar por:

```python
def save_spots_tracking(tracking_data: Dict[str, Dict[str, Any]]) -> None:
    """Persiste el tracking de cupos en SQLite."""
    conn = sqlite3.connect(DB_FILE)
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
    conn.commit()
    conn.close()
```

- [ ] **Step 11: Reemplazar clean_old_spots_tracking()**

Eliminar la función `clean_old_spots_tracking()` existente y reemplazar por:

```python
def clean_old_spots_tracking() -> None:
    """Elimina tracking de cupos de comps que ya no están en la tabla competitions."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM spots_tracking
        WHERE comp_id NOT IN (SELECT id FROM competitions)
    """)
    conn.commit()
    conn.close()
```

### 3e — Actualizar main() para usar initialize_database()

- [ ] **Step 12: Reemplazar las 3 llamadas de inicialización en main() por initialize_database()**

En la función `main()`, localizar las líneas (aproximadamente 1158-1160):
```python
initialize_data_file()
initialize_registration_tracking_file()
initialize_spots_tracking_file()
```

Reemplazarlas por:
```python
initialize_database()
```

- [ ] **Step 13: Verificar que el script ejecuta sin errores de sintaxis**

```bash
python -m py_compile main.py && echo "OK: sin errores de sintaxis"
```

Expected output: `OK: sin errores de sintaxis`

- [ ] **Step 14: Commit de la migración SQLite**

```bash
git add main.py
git commit -m "feat: migrate persistence from JSON files to SQLite"
```

---

## Task 4: Crear archivos Docker

**Files:**
- Create: `crontab`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Crear crontab**

Crear archivo `crontab` en la raíz del proyecto:

```
0 * * * * python /app/main.py
```

(Sin salto de línea adicional al final — supercronic es estricto con el formato)

- [ ] **Step 2: Crear Dockerfile**

Crear archivo `Dockerfile` en la raíz del proyecto:

```dockerfile
FROM python:3.12-slim

# Instalar supercronic
ARG SUPERCRONIC_VERSION=0.2.33
ARG SUPERCRONIC_SHA1SUM=3eb8e8a33f225a0ac5e685adabcb1db1e5b03e53
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fsSLO "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-amd64" && \
    echo "${SUPERCRONIC_SHA1SUM}  supercronic-linux-amd64" | sha1sum -c - && \
    chmod +x supercronic-linux-amd64 && \
    mv supercronic-linux-amd64 /usr/local/bin/supercronic && \
    apt-get remove -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

CMD ["supercronic", "/app/crontab"]
```

- [ ] **Step 3: Crear docker-compose.yml**

Crear archivo `docker-compose.yml` en la raíz del proyecto:

```yaml
services:
  wca-tracker:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
```

- [ ] **Step 4: Crear .env.example**

Crear archivo `.env.example` en la raíz del proyecto:

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXXXX/YYYYY
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHANNEL_ID=your_channel_id_here
DB_PATH=/app/data/wca_tracker.sqlite3
```

- [ ] **Step 5: Commit de archivos Docker**

```bash
git add Dockerfile docker-compose.yml crontab .env.example
git commit -m "feat: add Docker Compose setup with supercronic"
```

---

## Task 5: Eliminar workflow de GitHub Actions

**Files:**
- Delete: `.github/workflows/main.yml`

- [ ] **Step 1: Eliminar el workflow**

```bash
git rm .github/workflows/main.yml
```

- [ ] **Step 2: Verificar que no queden archivos en .github/workflows/**

```bash
git status
```

Expected: `.github/workflows/main.yml` aparece como `deleted`.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove GitHub Actions workflow"
```

---

## Task 6: Verificación local del build Docker

**Prerequisito:** Tener Docker disponible en la máquina local o en el servidor.

- [ ] **Step 1: Crear archivo .env local con valores reales**

```bash
cp .env.example .env
# Editar .env con los valores reales de Discord/Telegram
```

- [ ] **Step 2: Crear directorio data/**

```bash
mkdir -p data
```

- [ ] **Step 3: Construir la imagen Docker**

```bash
docker compose build
```

Expected: build exitoso sin errores. La imagen descarga supercronic y las dependencias Python.

- [ ] **Step 4: Ejecutar el script una vez para verificar**

```bash
docker compose run --rm wca-tracker python /app/main.py
```

Expected: el script corre, crea `data/wca_tracker.sqlite3`, consulta la API de WCA y (si hay competencias nuevas) envía notificaciones. Los logs no deben mostrar excepciones.

- [ ] **Step 5: Verificar que el SQLite se creó en data/**

```bash
ls -la data/
```

Expected: `wca_tracker.sqlite3` presente con tamaño > 0 bytes.

- [ ] **Step 6: Levantar el servicio en modo daemon**

```bash
docker compose up -d
```

- [ ] **Step 7: Verificar que el servicio está corriendo**

```bash
docker compose ps
docker compose logs wca-tracker
```

Expected: servicio `wca-tracker` en estado `running`. Logs muestran que supercronic cargó el crontab correctamente.

---

## Deploy en el servidor

Una vez que la verificación local pasa, el proceso de deploy inicial en el servidor es:

```bash
# En el servidor
git clone <repo-url> wca-dc-webhook
cd wca-dc-webhook
cp .env.example .env
# Editar .env con los valores reales
nano .env

mkdir -p data
docker compose up -d
docker compose logs -f   # verificar que arrancó bien
```

Para actualizaciones futuras:
```bash
git pull
docker compose up -d --build
```
