#!/bin/sh
set -eu

umask 077

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <commit-sha> <app-image> <nginx-image>" >&2
  exit 1
fi

release=$1
BOOKER_TEE_IMAGE=$2
BOOKER_TEE_NGINX_IMAGE=$3
case "$release" in *[!0-9a-f]* | "") echo "Invalid commit SHA." >&2; exit 1 ;; esac
if [ "${#release}" -ne 40 ]; then
  echo "Invalid commit SHA." >&2
  exit 1
fi
case "$BOOKER_TEE_IMAGE$BOOKER_TEE_NGINX_IMAGE" in
  *[!A-Za-z0-9_./:@-]*) echo "Invalid image reference." >&2; exit 1 ;;
esac
case "$BOOKER_TEE_IMAGE:$BOOKER_TEE_NGINX_IMAGE" in
  ghcr.io/*:"$release":ghcr.io/*:"$release") ;;
  *) echo "Images must use the release SHA tag from GHCR." >&2; exit 1 ;;
esac

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(dirname -- "$script_dir")
BOOKER_TEE_ENV_FILE=${BOOKER_TEE_ENV_FILE:-/etc/booker-tee/production.env}
backup_root=${BOOKER_TEE_BACKUP_ROOT:-/var/backups/booker-tee}
export BOOKER_TEE_ENV_FILE BOOKER_TEE_IMAGE BOOKER_TEE_NGINX_IMAGE

exec 9>"${BOOKER_TEE_DEPLOY_LOCK_FILE:-/tmp/booker-tee-production-deploy.lock}"
if ! flock -n 9; then
  echo "Another production deployment is running." >&2
  exit 1
fi

cd "$project_root"
if [ "$(git rev-parse HEAD)" != "$release" || ! git merge-base --is-ancestor "$release" origin/main; then
  echo "Release must be the checked-out commit from origin/main." >&2
  exit 1
fi

compose() {
  docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml "$@"
}

compose config -q
compose pull app parser upload-cleanup nginx
./scripts/production-preflight.sh

if [ -n "$(compose ps --status running -q app)" ]; then
  backup_dir="$backup_root/$(date -u '+%Y%m%dT%H%M%SZ')-$release"
  ./scripts/backup.sh "$backup_dir"
fi

compose stop nginx app upload-cleanup
compose up -d --wait postgres parser
compose run --rm app alembic upgrade head
compose up -d --wait
compose run --rm --no-deps app python -m app.features.chat_integrations.webhook

echo "Production deployment completed: $release"
