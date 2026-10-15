# Build from the repository root, because the app reads data/ and knowledge/ beside backend/:
#   docker build -f backend/Dockerfile -t campus-copilot-backend .

# --- builder: install the dependencies into a virtual environment
FROM python:3.14-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
COPY backend/requirements.txt /tmp/requirements.txt
RUN /opt/venv/bin/pip install -r /tmp/requirements.txt

# --- runtime: only what is needed to run
FROM python:3.14-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/app \
    DATABASE_URL=sqlite:////var/lib/campus/campus.db \
    CHROMA_DIR=/var/lib/campus/chroma \
    KNOWLEDGE_UPLOAD_DIR=/var/lib/campus/uploads \
    FASTEMBED_CACHE_PATH=/home/app/.cache/fastembed
# A user with no shell and no write access to the code. The data and model folders are its own.
RUN useradd --create-home --home-dir /home/app --shell /usr/sbin/nologin app \
    && mkdir -p /var/lib/campus/chroma /var/lib/campus/uploads /home/app/.cache \
    && chown -R app:app /var/lib/campus /home/app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app/backend
COPY backend/alembic.ini backend/pytest.ini ./
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/rag_eval ./rag_eval
COPY data /app/data
COPY knowledge /app/knowledge
COPY backend/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
USER app
EXPOSE 8000
# The search models (about 170 MB) download on first use into /home/app/.cache: keep it on a volume.
VOLUME ["/var/lib/campus", "/home/app/.cache"]
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- dev: the same image plus the test tools; compose mounts the code over /app/backend/app and reloads on change
FROM runtime AS dev
USER root
COPY backend/requirements-dev.txt /tmp/requirements-dev.txt
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt
COPY backend/tests ./tests
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
