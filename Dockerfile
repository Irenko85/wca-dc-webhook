FROM python:3.12-slim

# Crear usuario no-root
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Crear directorio de datos y asignar ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

CMD ["sh", "-c", "while true; do /usr/local/bin/python -u /app/main.py; sleep 3600; done"]
