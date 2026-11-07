#!/bin/sh
set -e

# Apply migrations (the DB is ready — compose waits on its healthcheck).
python manage.py migrate --noinput

# Optionally seed the baseline store/aisles/bays/assumptions on first start.
if [ "$SEED_ON_START" = "true" ]; then
  python manage.py seed \
    --username "${SEED_USER:-demo}" \
    --password "${SEED_PASSWORD:-demo12345}" || true
fi

exec gunicorn config.wsgi --bind 0.0.0.0:8000 --workers 3
