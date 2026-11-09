#!/bin/sh
# Container start-up: wait for MySQL, apply migrations, optionally seed, then start the app.
set -e

echo "Waiting for the database..."
python - <<'PY'
import sys
import time

from pydantic import ValidationError

try:
    from app.core.database import ping_database
except ValidationError as exc:
    # Print only the reasons, never the setting values (they include secrets).
    for error in exc.errors():
        name = ".".join(str(part) for part in error["loc"]).upper()
        reason = error["msg"].removeprefix("Value error, ")
        print(f"Configuration error: {name + ': ' if name else ''}{reason}", file=sys.stderr)
    sys.exit(1)

for attempt in range(1, 61):
    if ping_database():
        print("Database is ready.")
        sys.exit(0)
    time.sleep(2)
print("Database did not become ready in time.", file=sys.stderr)
sys.exit(1)
PY

echo "Applying database migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ]; then
    echo "Loading sample data (safe to repeat: existing rows are skipped)..."
    python -m db.seed
fi

echo "Starting: $*"
exec "$@"
