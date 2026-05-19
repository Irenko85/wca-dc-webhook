# Design Spec: Migración a Docker en servidor propio

**Fecha:** 2026-05-18  
**Proyecto:** wca-dc-webhook  
**Estado:** Aprobado

---

## Contexto

El proyecto `wca-dc-webhook` es un script Python que consulta la API de la WCA cada hora, detecta nuevas competencias de speedcubing en Chile y envía notificaciones a Discord y Telegram.

Actualmente corre como **GitHub Action programada** (`cron: "0 * * * *"`). El archivo SQLite de estado (`wca_tracker.sqlite3`) se commitea al repositorio después de cada ejecución para persistir el estado entre corridas.

Este diseño migra la ejecución al **servidor propio del usuario** usando Docker Compose, eliminando la dependencia de GitHub Actions y el anti-patrón de versionar la base de datos en git.

---

## Objetivo

- Correr el script en un servidor propio (Ubuntu Server con Docker)
- Persistir el SQLite en el servidor (no en el repo)
- Deploy y actualizaciones simples (`git pull && docker compose up -d --build`)
- Eliminar el workflow de GitHub Actions

---

## Arquitectura

### Stack
- **Runtime:** Python 3.12-slim
- **Scheduler:** [supercronic](https://github.com/aptible/supercronic) (cron purpose-built para contenedores)
- **Orquestación:** Docker Compose
- **Persistencia:** SQLite en bind mount `./data/`

### Estructura de archivos resultante

```
wca-dc-webhook/
├── Dockerfile
├── docker-compose.yml
├── crontab                         ← schedule de supercronic
├── .env.example
├── .gitignore                      ← actualizado: agrega data/ y .env
├── main.py                         ← un solo cambio: ruta de DB
├── requirements.txt
└── data/                           ← gitignored, persiste en el servidor
    └── wca_tracker.sqlite3
```

### Archivos eliminados
- `.github/workflows/main.yml`

---

## Componentes

### Dockerfile

```dockerfile
FROM python:3.12-slim

# Instalar supercronic
ARG SUPERCRONIC_VERSION=0.2.33
ARG SUPERCRONIC_SHA1SUM=3eb8e8a33f225a0ac5e685adabcb1db1e5b03e53
RUN apt-get update && apt-get install -y curl && \
    curl -fsSLO "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-amd64" && \
    echo "${SUPERCRONIC_SHA1SUM}  supercronic-linux-amd64" | sha1sum -c - && \
    chmod +x supercronic-linux-amd64 && \
    mv supercronic-linux-amd64 /usr/local/bin/supercronic && \
    apt-get remove -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

CMD ["supercronic", "/app/crontab"]
```

### docker-compose.yml

```yaml
services:
  wca-tracker:
    build: .
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
```

### crontab (supercronic)

```
0 * * * * python /app/main.py
```

### .env.example

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHANNEL_ID=your_channel_id_here
DB_PATH=/app/data/wca_tracker.sqlite3
```

---

## Cambios en main.py

Un único cambio: la ruta del archivo SQLite debe leerse desde la variable de entorno `DB_PATH`, con fallback a `wca_tracker.sqlite3` para compatibilidad local.

**Línea afectada:** donde se define la constante `DB_FILE` o similar (verificar en código actual).

```python
import os
DB_FILE = os.getenv("DB_PATH", "wca_tracker.sqlite3")
```

---

## Cambios en .gitignore

Agregar:
```
.env
data/
```

---

## Flujo de deploy inicial en el servidor

```bash
git clone <repo-url> && cd wca-dc-webhook
cp .env.example .env          # completar con valores reales
mkdir -p data
docker compose up -d
docker compose logs -f        # verificar que corre correctamente
```

## Flujo de actualización

```bash
git pull
docker compose up -d --build
```

---

## Criterios de aceptación

- [ ] `docker compose up -d` levanta el servicio sin errores
- [ ] El log muestra ejecución exitosa del script en el primer ciclo
- [ ] El archivo `data/wca_tracker.sqlite3` se crea y persiste entre reinicios
- [ ] Las notificaciones de Discord y Telegram se envían correctamente
- [ ] El directorio `data/` está en `.gitignore` y no se sube al repo
- [ ] El workflow de GitHub Actions ya no existe en el repo
- [ ] `main.py` usa `DB_PATH` de env var con fallback local

---

## Lo que NO cambia

- La lógica de negocio de `main.py` (consultas a WCA, detección de cambios, notificaciones)
- El esquema de la base de datos SQLite
- Las variables de entorno de Discord y Telegram existentes
- `requirements.txt`
