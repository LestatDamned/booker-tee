#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or is not available in PATH."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose is not available."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed, but the Docker daemon is not running."
  exit 1
fi

if [ "${1:-}" != "--yes" ]; then
  echo "This will stop Booker Tee and delete local alpha database, uploads, and cached app environment."
  echo "Run this command only if you want a clean local alpha start:"
  echo ""
  echo "  ./scripts/alpha-reset.sh --yes"
  exit 1
fi

echo "Resetting Booker Tee alpha local data..."
docker compose down --volumes --remove-orphans
echo "Local alpha data was removed. Start again with ./scripts/alpha-up.sh"
