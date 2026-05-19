FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data

CMD ["sh", "-c", "while true; do /usr/local/bin/python -u /app/main.py; sleep 3600; done"]
