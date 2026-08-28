# Production runbook

Статус: repository hardening выполнен; первый внешний release требует VPS,
реальные secrets, TLS, email/Telegram credentials и smoke.

Целевая схема — один VPS:

```text
Internet -> Nginx 80/443 -> FastAPI + React :8000 -> PostgreSQL
                               -> isolated parser over Unix socket
```

PostgreSQL не публикуется наружу. Kubernetes, Redis, Celery и отдельный frontend
server не требуются.

## Подготовка

1. Создать отдельного Unix user и каталог deployment.
2. Установить Docker Engine/Compose и включить firewall только для SSH/80/443.
3. Создать untracked production env file с mode `600`.
4. Настроить DNS `BOOKER_TEE_DOMAIN`.
5. Подготовить persistent PostgreSQL/uploads volumes и внешний каталог backup.
6. Получить TLS certificate и настроить renewal.
7. Настроить SMTP и Telegram только если эти integrations включаются.

Минимальные security settings:

```env
BOOKER_TEE_ENVIRONMENT=production
BOOKER_TEE_DEBUG=false
BOOKER_TEE_REGISTRATION_MODE=invite_only
BOOKER_TEE_AUTH_SECRET_KEY=<random 32+ chars>
BOOKER_TEE_SESSION_COOKIE_SECURE=true
BOOKER_TEE_ALLOWED_HOSTS=finance.example
BOOKER_TEE_DOMAIN=finance.example
BOOKER_TEE_PUBLIC_BASE_URL=https://finance.example
BOOKER_TEE_SECURITY_HEADERS_ENABLED=true
BOOKER_TEE_UPLOAD_RETENTION_HOURS=48
```

Production preflight проверяет полный набор обязательных значений; этот список
не заменяет `.env.example` и Compose contract.

## Перед релизом

```bash
export BOOKER_TEE_ENV_FILE=/absolute/path/production.env
chmod 600 "$BOOKER_TEE_ENV_FILE"
./scripts/production-preflight.sh
./scripts/release-gate.sh
```

Дополнительно должны пройти dependency/image audits и обычные backend/frontend
checks. Не публиковать image с известной исправляемой critical/high
уязвимостью.

Создать backup до изменения работающей среды:

```bash
./scripts/backup.sh /absolute/path/new-backup-directory
```

Backup script останавливает app на время consistent PostgreSQL dump, записывает
image, Alembic revision, manifest и checksums. Temporary original uploads в
backup не входят по текущей retention policy.

## Release

GitHub Actions workflow `Release Gate` сначала публикует app/nginx images с
тегом commit SHA. Опция `deploy` запускает production deployment только после
успешного gate; VPS получает application secrets только из локального env file.
GitHub environment `production` хранит только `VPS_HOST`, `VPS_PORT`,
`VPS_USER`, `VPS_KNOWN_HOSTS` и `VPS_SSH_PRIVATE_KEY`.

```text
backup
  -> build immutable app/nginx images
  -> start/wait PostgreSQL
  -> alembic upgrade head
  -> start/wait app
  -> internal health check
  -> bootstrap first owner when database is empty
  -> start Nginx/TLS
  -> configure Telegram webhook when enabled
  -> production smoke
  -> invite first users
```

Используйте explicit image tags; не заменяйте работающий release неизвестным
`latest`. Migration запускается до переключения traffic. Production health
доступен через public `/health`; database health не публикуется наружу.

## Smoke

Проверить:

- HTTPS redirect, certificate, security headers и strict CSP;
- login/invite-only signup/email verification;
- workspace/account/manual income-expense-transfer;
- sanitized statement upload, mapping/review и duplicate protection;
- reports/XLSX;
- Telegram link/webhook/upload, если включён;
- отсутствие raw data/tokens в access и application logs;
- mobile/keyboard critical flow.

Первый release проводить для ограниченного числа пользователей.

## Rollback

- Сохранить предыдущие immutable app/nginx images.
- Откатывать code image только при совместимой schema.
- Не выполнять автоматический Alembic downgrade.
- При несовместимой migration остановить traffic и восстановить заранее
  проверенный backup в чистую среду.
- После incident отозвать затронутые session/Telegram/SMTP credentials.

Restore rehearsal:

```bash
BOOKER_TEE_ENV_FILE=/absolute/path/production.env \
  ./scripts/restore-backup.sh /absolute/path/backup booker-tee-restore-test
```

Restore script принимает только новый project `booker-tee-restore-*`, проверяет
permissions, checksums, manifest, empty database и Alembic revision. Не
используйте его поверх production volumes.

## Эксплуатация

- ежедневно проверять создание backup и свободное место;
- регулярно выполнять restore rehearsal;
- следить за availability, 5xx, rate-limit rejects, disk и certificate expiry;
- проверять hourly cleanup временных originals;
- проверять status/restart count `parser` и `upload-cleanup`, сообщения
  `partial_failure`, 429/timeout/OOM classification и свободное место uploads
  volume;
- подтверждать, что parser не получает secrets, networks или uploads mount;
- обновлять OS/base images и повторять dependency/image audit перед release;
- хранить backup отдельно от VPS и шифровать storage;
- не отправлять raw documents или финансовые payloads во внешний monitoring.

Любая команда, меняющая production state, выполняется только после точного
разрешения target project/env file и актуального backup.
