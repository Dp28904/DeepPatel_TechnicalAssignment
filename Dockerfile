# Application image: Python 3.12 + FastAPI app served by uvicorn.
# Build and run everything with:  docker compose up --build
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first, so this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code (tests, docs and local files are excluded by .dockerignore).
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY db ./db
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

# Run as an unprivileged user, never as root.
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import os,urllib.request,sys; port=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=4).status == 200 else 1)"

ENTRYPOINT ["entrypoint.sh"]
# PORT is set by hosting platforms such as Render; 8000 is the local default.
# --forwarded-allow-ips trusts the platform's proxy for the real client scheme (https).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
