FROM python:3.12-slim

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid "${APP_GID}" app && \
    useradd --uid "${APP_UID}" --gid app --create-home app

COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN mkdir -p /app/data && chown -R app:app /app/data

USER app

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD ["python", "-m", "wca_notifier.healthcheck"]

CMD ["python", "-m", "wca_notifier"]
