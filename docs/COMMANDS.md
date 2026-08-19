# Справочник CLI-команд Booker Tee

Этот файл — единая точка входа для локальных, deployment и эксплуатационных
команд. Если команда меняет production-состояние, это указано явно. Все команды
запускаются из корня репозитория, кроме блоков с `cd frontend`.

## 1. Локальный alpha-запуск

Linux/macOS:

```bash
./scripts/alpha-up.sh
./scripts/alpha-up.sh --detach
./scripts/alpha-down.sh
```

Windows PowerShell:

```powershell
.\scripts\alpha-up.ps1
.\scripts\alpha-up.ps1 --detach
.\scripts\alpha-down.ps1
```

`alpha-up` создаёт локальный `.env` из `.env.example`, если файла ещё нет,
собирает образы и запускает приложение. `--detach` запускает его в фоне.
`alpha-down` останавливает контейнеры, но сохраняет базу и uploads.

Полностью удалить только локальные alpha-данные:

```bash
./scripts/alpha-reset.sh --yes
```

```powershell
.\scripts\alpha-reset.ps1 --yes
```

Команда удаляет локальные Docker volumes с базой и uploads. Для production она
не используется.

Логи и состояние локальных контейнеров:

```bash
docker compose ps
docker compose logs --tail=200 app
docker compose logs -f app
```

## 2. Локальная разработка без application container

Запустить только PostgreSQL, применить миграции и поднять FastAPI на host:

```bash
docker compose up -d postgres
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend development server:

```bash
cd frontend
npm ci
npm run dev
```

Локальный Telegram polling используется только для разработки:

```bash
uv run python -m app.features.chat_integrations.polling
```

Регистрация webhook по настройкам текущего environment:

```bash
uv run python -m app.features.chat_integrations.webhook
```

## 3. Production: обязательная подготовка shell

Production env хранится вне Git и доступен только владельцу:

```bash
export BOOKER_TEE_ENV_FILE=/etc/booker-tee/booker-tee.env
export BOOKER_TEE_DOMAIN=finance.example.com
chmod 600 "$BOOKER_TEE_ENV_FILE"
```

Для immutable application image используется Git revision:

```bash
export BOOKER_TEE_IMAGE=booker-tee:$(git rev-parse --short HEAD)
export BOOKER_TEE_NGINX_IMAGE=booker-tee-nginx:$(git rev-parse --short HEAD)
```

Не вставляйте секреты непосредственно в команды: они сохраняются в shell
history и могут попасть в process list.

## 4. Production: проверка и сборка

Проверить итоговую Compose-конфигурацию:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml config -q
```

Собрать application и Nginx images:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml build app nginx
```

Проверить production-настройки и безопасность env-файла до миграций:

```bash
./scripts/production-preflight.sh
```

Preflight не подключается к SMTP или Telegram и не выводит значения секретов.

## 5. Первый production-запуск

Точный порядок первого релиза описан в
[`deploy/plan/README.md`](deploy/plan/README.md). Команды выполняются по одной и
следующий шаг запускается только после успешного предыдущего.

Запустить PostgreSQL:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml up -d postgres
```

Применить миграции отдельным one-off container:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  run --rm app alembic upgrade head
```

Первично получить Let's Encrypt certificate. DNS уже должен указывать на VPS,
а host port `80` должен быть свободен:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  run --rm --service-ports certbot
```

Запустить весь production stack:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml up -d
```

Создать первого owner после миграций. Команда интерактивно и без echo запросит
пароль; повторный bootstrap запрещён:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  run --rm app python -m app.features.users.bootstrap
```

Зарегистрировать production Telegram webhook:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  run --rm app python -m app.features.chat_integrations.webhook
```

Проверить внешний health endpoint:

```bash
curl --fail --silent --show-error "https://$BOOKER_TEE_DOMAIN/health"
```

## 6. Обычный production-релиз

После создания backup и прохождения release checks:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml build app nginx
./scripts/production-preflight.sh && \
  docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  run --rm app alembic upgrade head && \
  docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml up -d
```

Оператор использует `&&`, чтобы новая версия не запускалась после ошибки
preflight или миграции. Предыдущий image tag сохраняется для rollback кода без
автоматического Alembic downgrade.

## 7. Production-обслуживание

Создать новый backup set PostgreSQL. Каталог назначения не должен существовать;
скрипт не включает временные originals и не перезаписывает готовые копии:

```bash
export BOOKER_TEE_ENV_FILE=/etc/booker-tee/booker-tee.env
./scripts/backup.sh /var/backups/booker-tee/2026-08-19T120000Z
```

Почасовая очистка временных originals и Telegram file metadata:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  exec -T app python -m app.features.imports.documents.source_cleanup
```

Команда идемпотентна. Она удаляет originals по retention policy, но сохраняет
document metadata, raw data и ledger records. Ненулевой exit code означает
частичный сбой и требует проверки логов.

Обновить сертификаты и перезагрузить Nginx:

```bash
./docker/renew-certificates.sh
```

Проверить renewal без изменения сертификатов:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  run --rm certbot renew --dry-run --webroot --webroot-path /var/www/certbot
```

Состояние, логи и healthchecks:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml ps
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml logs --tail=200 app nginx postgres
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml logs -f app nginx
```

Безопасно пересоздать application container из выбранного image:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  up -d --no-deps --force-recreate app
```

Остановить production containers с сохранением volumes:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml down
```

Никогда не запускайте для production `docker compose down --volumes` или
`docker compose down -v`: это удаляет PostgreSQL и uploads volumes. Не выполняйте
автоматический `alembic downgrade`; восстановление несовместимой схемы делается
только через заранее проверенный backup/restore.

## 8. Backend-проверки

```bash
uv sync
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

Проверка production Python dependencies:

```bash
uv export --frozen --no-dev --no-emit-project --format requirements-txt \
  --output-file /tmp/booker-tee-release-requirements.txt
uvx pip-audit -r /tmp/booker-tee-release-requirements.txt
```

## 9. Frontend-проверки

```bash
cd frontend
npm ci
npm run check
npm audit --omit=dev
```

Отдельные frontend-команды:

```bash
npm run format
npm run format:check
npm run lint
npm run styles:check
npm run api:generate
npm run api:check
npm run typecheck
npm run test
npm run build
```

## 10. Вспомогательные команды разработчика

Экспортировать OpenAPI contract:

```bash
uv run python scripts/export_openapi.py frontend/openapi.json
```

Запустить UI audit или посмотреть его параметры:

```bash
uv run python scripts/ui_audit.py --help
uv run python scripts/ui_audit.py --check-csp
uv run python scripts/ui_audit.py
uv run python scripts/ui_audit.py --scenario realistic
uv run python scripts/ui_audit.py --scenario review_interactions
uv run python scripts/ui_audit.py --authenticated --scenario review_interactions \
  --path react-import-review --viewport desktop
uv run python scripts/ui_audit.py --scenario design_audit
uv run python scripts/ui_audit.py --scenario theme_audit --theme catppuccin-latte
```

## 11. Правило обновления справочника

При добавлении нового исполняемого файла в `scripts/` или `docker/`, нового
`python -m app...` entrypoint либо production-команды сначала обновляется этот
справочник. Подробные причины и exit gates остаются в профильной документации;
здесь хранится только назначение и безопасный способ запуска.
