# ChemReady web app. Builds a small image that runs the FastAPI app on port 7860
# (the port Hugging Face Spaces expects; override with PORT).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app
RUN pip install --no-cache-dir "uv==0.11.32"

# Install dependencies first (cached unless the lock file changes), then the code.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

# Run as a normal user, never root. Data lives in /data (mount a volume to keep it).
RUN useradd --create-home --uid 1000 app && mkdir -p /data && chown -R app /data
USER app

ENV CHEMREADY_ENVIRONMENT=production \
    CHEMREADY_DATABASE_PATH=/data/chemready.sqlite \
    CHEMREADY_UPLOAD_DIR=/data/uploads \
    CHEMREADY_LOG_FORMAT=json \
    PORT=7860

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz')"

# CHEMREADY_DEMO=true creates the demo account with fictional SDS files at start-up.
CMD ["sh", "-c", "if [ \"$CHEMREADY_DEMO\" = \"true\" ]; then /app/.venv/bin/chemready seed-demo; fi; exec /app/.venv/bin/uvicorn --factory chemready.app.main:app_factory --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips='*'"]
