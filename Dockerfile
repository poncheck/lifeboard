FROM python:3.12-slim

RUN useradd --create-home --uid 1000 lifeboard \
    && apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY . .

RUN mkdir -p backend/data && chown -R lifeboard:lifeboard /app \
    && chmod +x docker-entrypoint.sh

EXPOSE 8420

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8420/healthz')" || exit 1

# Container starts as root (not USER lifeboard) so the entrypoint can
# fix ownership on bind-mounted volumes before dropping to the
# unprivileged user — see docker-entrypoint.sh for why this matters.
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "backend.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8420"]
