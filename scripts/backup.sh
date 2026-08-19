#!/bin/sh
set -eu

umask 077

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(dirname -- "$script_dir")
: "${BOOKER_TEE_ENV_FILE:?Set BOOKER_TEE_ENV_FILE to the production environment file}"

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/new-backup-directory" >&2
  exit 1
fi
if [ ! -f "$BOOKER_TEE_ENV_FILE" ]; then
  echo "Backup failed: environment file does not exist." >&2
  exit 1
fi

env_file=$(realpath -- "$BOOKER_TEE_ENV_FILE")
if [ "$(stat -c '%a' -- "$env_file")" != "600" ]; then
  echo "Backup failed: environment file permissions must be 600." >&2
  exit 1
fi
backup_dir=$1
backup_project=${BOOKER_TEE_BACKUP_PROJECT:-booker-tee-production}
case "$backup_project" in
  booker-tee-production | booker-tee-backup-source-?*) ;;
  *)
    echo "Backup failed: unsupported Compose project name." >&2
    exit 1
    ;;
esac
case "$backup_project" in
  *[!a-z0-9_-]*)
    echo "Backup failed: Compose project name contains unsupported characters." >&2
    exit 1
    ;;
esac
if [ -e "$backup_dir" ]; then
  echo "Backup failed: destination already exists: $backup_dir" >&2
  exit 1
fi

compose() {
  docker compose --project-name "$backup_project" --env-file "$env_file" \
    -f "$project_root/compose.production.yaml" "$@"
}

app_container=$(compose ps --status running -q app)
if [ -z "$app_container" ]; then
  echo "Backup failed: production app container is not running." >&2
  exit 1
fi
application_image=$(docker inspect --format '{{.Config.Image}}' "$app_container")
case "$application_image" in
  "" | *[!A-Za-z0-9_./:@-]*)
    echo "Backup failed: could not determine a safe application image reference." >&2
    exit 1
    ;;
esac

mkdir -- "$backup_dir"
incomplete_marker="$backup_dir/INCOMPLETE"
: >"$incomplete_marker"
restart_app=0
restart_application() {
  if [ "$restart_app" -eq 1 ]; then
    compose start app >/dev/null
  fi
}
trap restart_application 0 1 2 15

restart_app=1
compose stop app >/dev/null
alembic_revision=$(compose exec -T postgres sh -c \
  'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT version_num FROM alembic_version"')
case "$alembic_revision" in
  "" | *[!A-Za-z0-9_]*)
    echo "Backup failed: database has no single valid Alembic revision." >&2
    exit 1
    ;;
esac

compose exec -T postgres sh -c \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl' \
  >"$backup_dir/postgresql.dump"

completed_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
printf '{\n  "format_version": 1,\n  "completed_at": "%s",\n  "application_image": "%s",\n  "alembic_revision": "%s",\n  "database_dump": "postgresql.dump",\n  "temporary_originals_included": false\n}\n' \
  "$completed_at" "$application_image" "$alembic_revision" \
  >"$backup_dir/manifest.json"
(
  cd "$backup_dir"
  sha256sum postgresql.dump manifest.json >SHA256SUMS
)

compose start app >/dev/null
restart_app=0
trap - 0 1 2 15
rm -- "$incomplete_marker"
echo "Backup completed: $backup_dir"
