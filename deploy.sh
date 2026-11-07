#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="docker compose -f docker-compose.prod.yml"
cd "$APP_DIR"
git fetch origin main
git reset --hard origin/main
$COMPOSE pull
$COMPOSE up -d
$COMPOSE exec -T backend python manage.py migrate --noinput
$COMPOSE exec -T backend python manage.py collectstatic --noinput
$COMPOSE ps
echo "Deployment completed successfully."
