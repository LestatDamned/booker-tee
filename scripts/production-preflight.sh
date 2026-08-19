#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(dirname -- "$script_dir")
: "${BOOKER_TEE_ENV_FILE:?Set BOOKER_TEE_ENV_FILE to the production environment file}"

if [ ! -f "$BOOKER_TEE_ENV_FILE" ]; then
  echo "Production preflight failed: environment file does not exist." >&2
  exit 1
fi

env_file=$(realpath -- "$BOOKER_TEE_ENV_FILE")
case "$env_file" in
  "$project_root"/*)
    relative_env_file=${env_file#"$project_root"/}
    if git -C "$project_root" ls-files --error-unmatch -- "$relative_env_file" >/dev/null 2>&1; then
      echo "Production preflight failed: environment file is tracked by Git." >&2
      exit 1
    fi
    ;;
esac

if [ "$(stat -c '%a' -- "$env_file")" != "600" ]; then
  echo "Production preflight failed: environment file permissions must be 600." >&2
  exit 1
fi

export BOOKER_TEE_ENV_FILE="$env_file"
exec docker compose --env-file "$env_file" -f "$project_root/compose.production.yaml" \
  run --rm --no-deps app python -m app.core.production_preflight
