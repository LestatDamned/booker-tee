#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(dirname -- "$script_dir")
: "${BOOKER_TEE_ENV_FILE:?Set BOOKER_TEE_ENV_FILE to the production environment file}"

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 /path/to/backup-directory booker-tee-restore-NAME" >&2
  exit 1
fi

backup_dir=$1
restore_project=$2
case "$restore_project" in
  booker-tee-restore-?*) ;;
  *)
    echo "Restore failed: project name must start with booker-tee-restore-." >&2
    exit 1
    ;;
esac
case "$restore_project" in
  *[!a-z0-9_-]*)
    echo "Restore failed: project name contains unsupported characters." >&2
    exit 1
    ;;
esac
if [ ! -f "$BOOKER_TEE_ENV_FILE" ]; then
  echo "Restore failed: environment file does not exist." >&2
  exit 1
fi

env_file=$(realpath -- "$BOOKER_TEE_ENV_FILE")
if [ "$(stat -c '%a' -- "$env_file")" != "600" ]; then
  echo "Restore failed: environment file permissions must be 600." >&2
  exit 1
fi
if [ ! -d "$backup_dir" ]; then
  echo "Restore failed: backup directory does not exist." >&2
  exit 1
fi
backup_dir=$(realpath -- "$backup_dir")
if [ "$(stat -c '%a' -- "$backup_dir")" != "700" ]; then
  echo "Restore failed: backup directory permissions must be 700." >&2
  exit 1
fi
if [ -e "$backup_dir/INCOMPLETE" ]; then
  echo "Restore failed: backup is marked INCOMPLETE." >&2
  exit 1
fi
for filename in postgresql.dump manifest.json SHA256SUMS; do
  if [ ! -f "$backup_dir/$filename" ]; then
    echo "Restore failed: backup is missing $filename." >&2
    exit 1
  fi
done
if ! (
  cd "$backup_dir"
  sha256sum postgresql.dump manifest.json | cmp - SHA256SUMS
); then
  echo "Restore failed: backup checksums do not match." >&2
  exit 1
fi
if ! grep -q '"temporary_originals_included": false' "$backup_dir/manifest.json"; then
  echo "Restore failed: manifest does not exclude temporary originals." >&2
  exit 1
fi

manifest_revision=$(sed -n \
  's/.*"alembic_revision": "\([A-Za-z0-9_]*\)".*/\1/p' \
  "$backup_dir/manifest.json")
case "$manifest_revision" in
  "" | *[!A-Za-z0-9_]*)
    echo "Restore failed: manifest has no single valid Alembic revision." >&2
    exit 1
    ;;
esac

postgres_volume="${restore_project}_booker_tee_postgres_data"
uploads_volume="${restore_project}_booker_tee_uploads"
for volume in "$postgres_volume" "$uploads_volume"; do
  if docker volume inspect "$volume" >/dev/null 2>&1; then
    echo "Restore failed: isolated volume already exists: $volume" >&2
    exit 1
  fi
done

compose() {
  docker compose --project-name "$restore_project" --env-file "$env_file" \
    -f "$project_root/compose.production.yaml" "$@"
}

compose up -d --wait postgres
public_tables=$(compose exec -T postgres sh -c \
  'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname = '\''public'\''"')
if [ "$public_tables" != "0" ]; then
  echo "Restore failed: destination database is not empty." >&2
  exit 1
fi

compose exec -T postgres sh -c \
  'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error --single-transaction --no-owner --no-acl' \
  <"$backup_dir/postgresql.dump"
restored_revision=$(compose exec -T postgres sh -c \
  'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT version_num FROM alembic_version"')
if [ "$restored_revision" != "$manifest_revision" ]; then
  echo "Restore failed: restored Alembic revision does not match manifest." >&2
  exit 1
fi

docker volume create \
  --label "com.docker.compose.project=$restore_project" \
  --label "com.docker.compose.volume=booker_tee_uploads" \
  "$uploads_volume" >/dev/null
echo "Restore completed in isolated Compose project: $restore_project"
