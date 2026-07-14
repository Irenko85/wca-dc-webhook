# Configurable and Reliable WCA Monitor Implementation Plan

> Implementation checklist for Codex. No commit or push is authorized by this plan.

**Goal:** Convert the Chile-first WCA notifier into a configurable, bilingual, self-hosted monitor that retries failed notification channels without duplicating successful deliveries.

**Architecture:** Introduce a small `run_cycle()` interface that coordinates WCA discovery, event detection, a durable SQLite notification outbox, and Discord/Telegram adapters. Move production code into `src/wca_notifier`, keep external systems behind injected adapters, and test behavior through the cycle and repository interfaces with temporary SQLite databases and fake external adapters.

**Tech Stack:** Python 3.12, pytest, Ruff, SQLite, requests, and Docker Compose.

---

No commit steps are included because commits require explicit user authorization.

### Task 1: Establish the test harness

**Files:**
- Create: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: `tests/test_monitor_cycle.py`

1. Configure the `src` package layout, pytest, Ruff, and package data for locale JSON files.
2. Add a competition fixture with registration and competitor-limit fields.
3. Write one failing integration-style test proving a failed Telegram delivery remains pending while a successful Discord delivery is not repeated.
4. Run `python -m pytest tests/test_monitor_cycle.py -v` and confirm RED because `run_cycle` and the outbox do not exist.

### Task 2: Add a durable notification outbox

**Files:**
- Create: `src/wca_notifier/__init__.py`
- Create: `src/wca_notifier/events.py`
- Create: `src/wca_notifier/repository.py`
- Create: `src/wca_notifier/monitor.py`
- Modify: `tests/test_monitor_cycle.py`

1. Define event types `competition_new`, `registration_upcoming`, `registration_open`, and `spots_limited`.
2. Implement an SQLite repository that creates idempotent events keyed by event type and competition ID.
3. Persist one delivery row per enabled channel and mark only successful channel deliveries.
4. Implement `run_cycle(settings, repository, wca_client, channels, now)` as the public interface.
5. Make the tracer test GREEN, then add vertical tests for a total delivery failure, a restart with pending delivery, and idempotent successful cycles.

### Task 3: Preserve and test event detection behavior

**Files:**
- Create: `src/wca_notifier/detection.py`
- Create: `tests/test_detection.py`

1. Add a failing test for a newly discovered competition.
2. Implement the minimal pure detector and make it pass.
3. Repeat RED/GREEN for registration opening within the configured window, registration just opened, and limited spots.
4. Inject `now` and the competitor-count lookup so tests never depend on the clock or live WCA endpoints.

### Task 4: Add validated runtime configuration

**Files:**
- Create: `src/wca_notifier/config.py`
- Create: `tests/test_config.py`
- Modify: `.env.example`

1. Test and implement validated settings for `WCA_COUNTRY_ISO2`, `TZ`, `NOTIFICATION_LANGUAGE`, `POLL_INTERVAL_SECONDS`, `REGISTRATION_UPCOMING_MINUTES`, `SPOTS_WARNING_PERCENT`, `DB_PATH`, and request timeout.
2. Preserve Chile defaults: `CL`, `America/Santiago`, and Spanish.
3. Validate ISO2, timezone, language, positive intervals, percentage range, and partial Telegram credentials.
4. Enable Discord and Telegram independently according to complete credentials.

### Task 5: Add English and Spanish message catalogs

**Files:**
- Create: `src/wca_notifier/locales/en.json`
- Create: `src/wca_notifier/locales/es.json`
- Create: `src/wca_notifier/i18n.py`
- Create: `tests/test_i18n.py`

1. Add a failing parity test requiring identical keys and placeholders in both catalogs.
2. Cover all current webhook messages rather than copying the historical bot catalog.
3. Test rendering for new competition, registration upcoming, registration open, and limited spots.
4. Keep one configured language per deployment; Portuguese remains outside the initial scope.

### Task 6: Split notification adapters

**Files:**
- Create: `src/wca_notifier/notifications/__init__.py`
- Create: `src/wca_notifier/notifications/formatting.py`
- Create: `src/wca_notifier/notifications/discord.py`
- Create: `src/wca_notifier/notifications/telegram.py`
- Create: `tests/test_notifications.py`

1. Test observable Discord payloads through a fake HTTP transport.
2. Implement event embeds without live network calls.
3. Test observable Telegram messages through a fake HTTP transport.
4. Implement safely escaped HTML messages and sanitized error logging.
5. Keep channel adapters independent so one failure cannot suppress another.

### Task 7: Move WCA and application entrypoints into the package

**Files:**
- Create: `src/wca_notifier/wca_client.py`
- Create: `src/wca_notifier/main.py`
- Create: `src/wca_notifier/__main__.py`
- Modify: `Dockerfile`
- Delete after replacement: root `main.py`, `config.py`, `database.py`, `detection.py`, `notifications.py`, `wca_api.py`

1. Move WCA and WCIF requests behind a client adapter.
2. Build real settings, repository, and channel adapters only in the composition root.
3. Execute cycles from the Python process with a configurable polling interval.
4. Run the full test suite after removing compatibility modules.

### Task 8: Clean legacy state and harden Docker

**Files:**
- Modify: `.gitignore`
- Modify: `.dockerignore`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Delete: `prev_comps.json`
- Delete: `registration_tracking.json`
- Delete: `spots_tracking.json`

1. Ignore SQLite files, test caches, virtual environments, and runtime data.
2. Install only runtime dependencies in the image and run as a non-root user.
3. Use an exec-form Python entrypoint with configurable polling rather than a shell loop.
4. Preserve the bind-mounted SQLite directory and log rotation.
5. Validate with `docker compose config`, image build, non-root inspection, and a controlled startup without external delivery.

### Task 9: Document local quality checks

1. Keep all GitHub Actions workflows absent from the repository.
2. Document pytest, Ruff, compilation, Docker build, and Compose validation commands.
3. Keep production execution exclusively on the self-hosted server.

### Task 10: Document the project and its history

**Files:**
- Create: `README.md`
- Create: `README.es.md`
- Modify: `docs/` only where current deployment information is stale.

1. Make English the primary README and link both languages at the top.
2. Explain the personal speedcubing problem, the 2023 Discord bot predecessor, and the evolution to a self-hosted multichannel monitor.
3. Document features, architecture, configuration, Docker usage, testing, reliability semantics, and roadmap.
4. State that Chile is the default use case while any WCA country ISO2 can be configured.

### Task 11: Final verification

1. Run `python -m pytest -v` and require all tests to pass.
2. Run `python -m ruff check .` and `python -m ruff format --check .`.
3. Run `python -m compileall -q src`.
4. Run `docker compose config`.
5. Build the image from scratch and verify its configured user is non-root.
6. Review `git diff --check`, `git status`, and the complete diff for secrets or accidental files.
7. Do not commit, push, archive `wca-bot`, change pinned repositories, or edit GitHub metadata without a separate explicit authorization.
