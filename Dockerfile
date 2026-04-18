FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CHROME_BINARY=/usr/bin/chromium \
    CHROME_HEADLESS=true \
    CHROME_NO_SANDBOX=true \
    CHROME_DISABLE_DEV_SHM_USAGE=true \
    ENABLE_BEEP=false \
    STATE_FILE=/app/state/last_seen.json \
    LOG_FILE=/app/logs/monitor.log \
    DIAGNOSTICS_DIR=/app/diagnostics

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        chromium \
        chromium-driver \
        fonts-liberation \
        fonts-noto-cjk \
        fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY monitor.py README.md PRD.md LICENSE .env.example ./

RUN mkdir -p /app/state /app/logs /app/diagnostics

VOLUME ["/app/state", "/app/logs", "/app/diagnostics"]

CMD ["python", "monitor.py"]
