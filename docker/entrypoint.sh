#!/bin/sh
# Container start-up: wait for MySQL, apply migrations, optionally seed, then start the app.
set -e

echo "Waiting for the database..."
python - <<'PY'
import sys
import time

from pydantic import ValidationError

try:
    from app.core.database import database_problem
except ValidationError as exc:
    # Print only the reasons, never the setting values (they include secrets).
    for error in exc.errors():
        name = ".".join(str(part) for part in error["loc"]).upper()
        reason = error["msg"].removeprefix("Value error, ")
        print(f"Configuration error: {name + ': ' if name else ''}{reason}", file=sys.stderr)
    sys.exit(1)

problem = None
for attempt in range(1, 61):
    problem = database_problem()
    if problem is None:
        print("Database is ready.")
        sys.exit(0)
    if attempt == 1 or attempt % 10 == 0:
        print(f"Database not reachable yet (attempt {attempt}/60): {problem}", file=sys.stderr)
    time.sleep(2)
print(f"Database did not become ready in time. Last error: {problem}", file=sys.stderr)
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
