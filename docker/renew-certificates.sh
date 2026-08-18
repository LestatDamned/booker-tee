#!/bin/sh
set -eu

: "${BOOKER_TEE_ENV_FILE:?Set BOOKER_TEE_ENV_FILE to the production environment file}"

docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
    run --rm certbot renew --webroot --webroot-path /var/www/certbot --quiet
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
    exec -T nginx nginx -s reload
