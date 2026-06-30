#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

detach=false
if [ "${1:-}" = "--detach" ] || [ "${1:-}" = "-d" ]; then
  detach=true
elif [ "${1:-}" != "" ]; then
  echo "Usage: ./scripts/alpha-up.sh [--detach]"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or is not available in PATH."
  echo "Install Docker Desktop, start it, then run this command again."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is not available."
  echo "Install a recent Docker Desktop version with Compose support."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed, but the Docker daemon is not running."
  echo "Start Docker Desktop, wait until it is ready, then run this command again."
  exit 1
fi

if [ ! -f .env.example ]; then
  echo ".env.example was not found. Run this script from a complete Booker Tee checkout."
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created local .env from .env.example."
fi

mkdir -p var/uploads

if [ -n "${BOOKER_TEE_APP_PORT:-}" ]; then
  app_port="$BOOKER_TEE_APP_PORT"
else
  app_port="$(grep -E '^BOOKER_TEE_APP_PORT=' .env 2>/dev/null | tail -n 1 | cut -d '=' -f 2- | tr -d '\r')"
fi
if [ -z "$app_port" ]; then
  app_port="8000"
fi
app_port="$(printf "%s" "$app_port" | sed "s/[[:space:]]//g; s/^['\"]//; s/['\"]$//")"

running_services=""
if running_services="$(docker compose ps --services --status running 2>/dev/null)"; then
  :
fi
app_already_running=false
for service in $running_services; do
  if [ "$service" = "app" ]; then
    app_already_running=true
  fi
done

if [ "$app_already_running" = false ] && command -v nc >/dev/null 2>&1; then
  if nc -z 127.0.0.1 "$app_port" >/dev/null 2>&1; then
    echo "Port ${app_port} is already in use."
    echo "Stop the other app or choose another port, for example:"
    echo ""
    echo "  BOOKER_TEE_APP_PORT=8010 ./scripts/alpha-up.sh"
    echo "  BOOKER_TEE_APP_PORT=8010 ./scripts/alpha-up.sh --detach"
    exit 1
  fi
fi

echo "Starting Booker Tee alpha locally..."
echo "Open http://127.0.0.1:${app_port} after Docker finishes building."

if [ "$detach" = true ]; then
  docker compose up --build --detach
  if command -v curl >/dev/null 2>&1; then
    echo "Waiting for Booker Tee healthcheck..."
    attempt=1
    while [ "$attempt" -le 60 ]; do
      if curl -fsS "http://127.0.0.1:${app_port}/health" >/dev/null 2>&1; then
        echo "Booker Tee is ready: http://127.0.0.1:${app_port}"
        echo "Stop it with ./scripts/alpha-down.sh"
        exit 0
      fi
      attempt=$((attempt + 1))
      sleep 2
    done
    echo "The app started, but /health did not respond in time."
    echo "Check logs with: docker compose logs app"
    exit 1
  fi
  echo "Booker Tee is starting in the background."
  echo "Stop it with ./scripts/alpha-down.sh"
  exit 0
fi

echo "Press Ctrl+C in this terminal to stop the app."
docker compose up --build
