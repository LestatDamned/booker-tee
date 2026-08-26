#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(dirname -- "$script_dir")
gate_project="booker-tee-release-gate-${GITHUB_RUN_ID:-local}"
gate_dir=$(mktemp -d)
env_file="$gate_dir/release-gate.env"
override_file="$gate_dir/compose.override.yaml"
cert_dir="$gate_dir/certificates"
domain=gate.booker.invalid
http_port=${BOOKER_TEE_GATE_HTTP_PORT:-18080}
https_port=${BOOKER_TEE_GATE_HTTPS_PORT:-18443}

compose() {
  docker compose --project-name "$gate_project" --env-file "$env_file" \
    -f "$project_root/compose.production.yaml" -f "$override_file" "$@"
}

cleanup() {
  compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf -- "$gate_dir"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$cert_dir/live/$domain"
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -subj "/CN=$domain" \
  -keyout "$cert_dir/live/$domain/privkey.pem" \
  -out "$cert_dir/live/$domain/fullchain.pem" >/dev/null 2>&1

umask 077
cat >"$env_file" <<EOF
POSTGRES_DB=booker_tee_gate
POSTGRES_USER=booker_tee
POSTGRES_PASSWORD=ci-only-database-password-never-production
DATABASE_URL=postgresql+asyncpg://booker_tee:ci-only-database-password-never-production@postgres:5432/booker_tee_gate
BOOKER_TEE_ENVIRONMENT=production
BOOKER_TEE_DEBUG=false
BOOKER_TEE_REGISTRATION_MODE=invite_only
BOOKER_TEE_AUTH_SECRET_KEY=ci-only-auth-key-never-production-32-characters
BOOKER_TEE_SESSION_COOKIE_SECURE=true
BOOKER_TEE_IDENTITY_EMAIL_ENABLED=true
BOOKER_TEE_IDENTITY_EMAIL_FROM=Booker Tee Gate <gate@booker.invalid>
BOOKER_TEE_SMTP_HOST=smtp.booker.invalid
BOOKER_TEE_SMTP_USERNAME=gate@booker.invalid
BOOKER_TEE_SMTP_PASSWORD=ci-only-smtp-password-never-production
BOOKER_TEE_SMTP_STARTTLS=true
BOOKER_TEE_ALLOWED_HOSTS=$domain
BOOKER_TEE_SECURITY_HEADERS_ENABLED=true
BOOKER_TEE_DOMAIN=$domain
BOOKER_TEE_CERTBOT_EMAIL=gate@booker.invalid
BOOKER_TEE_PUBLIC_BASE_URL=https://$domain
BOOKER_TEE_CHAT_INTEGRATIONS_ENABLED=true
BOOKER_TEE_TELEGRAM_BOT_TOKEN=ci-only-telegram-token-never-production
BOOKER_TEE_TELEGRAM_MODE=webhook
BOOKER_TEE_TELEGRAM_WEBHOOK_SECRET=ci_only_webhook_secret_never_production_123
BOOKER_TEE_UPLOAD_RETENTION_HOURS=48
BOOKER_TEE_HTTP_PORT=$http_port
BOOKER_TEE_HTTPS_PORT=$https_port
BOOKER_TEE_PROXY_SUBNET=10.254.253.0/24
BOOKER_TEE_ENV_FILE=$env_file
BOOKER_TEE_IMAGE=booker-tee:release-gate-${GITHUB_SHA:-local}
BOOKER_TEE_NGINX_IMAGE=booker-tee-nginx:release-gate-${GITHUB_SHA:-local}
BOOKER_TEE_GATE_CERTS_DIR=$cert_dir
EOF

cat >"$override_file" <<'EOF'
services:
  nginx:
    volumes:
      - ${BOOKER_TEE_GATE_CERTS_DIR:?Set BOOKER_TEE_GATE_CERTS_DIR}:/etc/letsencrypt:ro
EOF

compose config -q
compose build app nginx
compose run --rm --no-deps app python -m app.core.production_preflight
compose up -d --wait postgres
compose run --rm app alembic upgrade head
compose up -d --wait app nginx
compose exec -T parser python -c \
  'import os, tempfile; handle = tempfile.NamedTemporaryFile(); path = handle.name; assert os.stat(path).st_mode & 0o777 == 0o600; handle.close(); assert not os.path.exists(path)'

curl --fail --silent --show-error --insecure \
  --resolve "$domain:$https_port:127.0.0.1" "https://$domain:$https_port/health" \
  >/dev/null
test "$(curl --silent --output /dev/null --write-out '%{http_code}' \
  --header "Host: $domain" "http://127.0.0.1:$http_port/health")" = "301"
test "$(curl --silent --insecure --output /dev/null --write-out '%{http_code}' \
  --resolve "$domain:$https_port:127.0.0.1" "https://$domain:$https_port/health/db")" = "404"

upload_url="https://$domain:$https_port/api/v1/imports/documents"
dd if=/dev/zero of="$gate_dir/upload.bin" bs=1024 count=32 >/dev/null 2>&1
for request_number in 1 2 3; do
  curl --silent --insecure --output /dev/null --write-out '%{http_code}\n' \
    --resolve "$domain:$https_port:127.0.0.1" --limit-rate 4k \
    --request POST --data-binary "@$gate_dir/upload.bin" "$upload_url" \
    >"$gate_dir/concurrent-$request_number.status" &
done
wait
grep -q '^429$' "$gate_dir"/concurrent-*.status

for request_number in 1 2 3 4 5; do
  curl --silent --insecure --output /dev/null --write-out '%{http_code}\n' \
    --resolve "$domain:$https_port:127.0.0.1" --request POST "$upload_url" \
    >>"$gate_dir/sequential.status"
done
grep -q '^429$' "$gate_dir/sequential.status"

echo "Release gate passed."
