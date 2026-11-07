#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE="docker compose -f docker-compose.prod.yml"
cd "$APP_DIR"

git fetch origin main
git pull --ff-only origin main

$COMPOSE build --pull
$COMPOSE up -d --no-deps backend
$COMPOSE exec -T backend python manage.py migrate --noinput
$COMPOSE exec -T backend python manage.py collectstatic --noinput
$COMPOSE up -d --no-deps frontend
$COMPOSE up -d --remove-orphans
$COMPOSE ps
echo "Deployment completed successfully."
