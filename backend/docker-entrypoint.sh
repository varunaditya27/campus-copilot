#!/bin/sh
# Bring the database up to date, load the demo data into empty tables, optionally build the
# knowledge base, then run the command.
# Set RUN_MIGRATIONS=false when several copies start at once; run `alembic upgrade head` once instead.
set -e
# Without a fixed key every restart would sign everyone out, so refuse to start.
if [ -z "${JWT_SECRET:-}" ] && [ -z "${JWT_SECRET_FILE:-}" ]; then
    echo "Set JWT_SECRET or JWT_SECRET_FILE (openssl rand -hex 32)." >&2
    exit 1
fi
if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    alembic upgrade head
    python -m app.db.seed
fi
if [ "${RUN_INGEST:-false}" = "true" ]; then
    # Builds the knowledge base on first start; afterwards only changed documents are redone.
    python -m app.rag.ingest || echo "Knowledge base ingest failed: the assistant will say it is unavailable." >&2
fi
exec "$@"
