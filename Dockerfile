FROM python:3.12-slim

RUN useradd --create-home --uid 1000 lifeboard

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY . .

RUN mkdir -p backend/data && chown -R lifeboard:lifeboard /app

USER lifeboard

EXPOSE 8420

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8420/healthz')" || exit 1

CMD ["uvicorn", "backend.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8420"]
