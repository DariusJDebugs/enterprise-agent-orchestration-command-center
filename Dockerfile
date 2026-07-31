FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    DATABASE_PATH=/app/data/command_center.db \
    UPLOAD_DIR=/app/data/uploads \
    BACKUP_DIR=/app/data/backups \
    JSON_LOGS=true

RUN groupadd --system --gid 10001 eacc \
    && useradd --system --uid 10001 --gid eacc --home-dir /app --shell /usr/sbin/nologin eacc

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=eacc:eacc . .
RUN mkdir -p /app/data/uploads /app/data/backups \
    && chown -R eacc:eacc /app/data

USER 10001:10001
EXPOSE 8000
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/readiness', timeout=3)"

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
