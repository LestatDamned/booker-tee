# План первого production-деплоя

Статус: active.

Цель — безопасно опубликовать Booker Tee для ограниченного круга пользователей,
с регистрацией только по приглашениям и рабочей Telegram-интеграцией.

План рассчитан на один VPS:

```text
Internet
  -> Nginx container (80/443, TLS, rate limits)
  -> FastAPI + React build (app:8000, private proxy network)
  -> PostgreSQL (private Docker network)
  -> upload storage (persistent volume)
```

На первом этапе не нужны Kubernetes, Redis, Celery, отдельный frontend-сервер
или микросервисная архитектура.

## 1. Закрыть блокирующие уязвимости

Baseline от 2026-08-18:

- `npm audit --omit=dev` обнаружил high severity в `react-router 8.2.0`;
- `pip-audit` обнаружил исправляемые уязвимости в:
  - `cryptography 49.0.0`, fix version `50.0.0`;
  - `Pillow 12.2.0`, fix version `12.3.0`;
  - `pydantic-settings 2.14.1`, fix version `2.14.2`.

Работы:

1. Обновить уязвимые зависимости и lock-файлы.
2. Проверить импорт PDF/XLSX, авторизацию и React routing.
3. Повторить dependency audit после обновления.

Exit gate:

```bash
npm audit --omit=dev
uvx pip-audit -r <production-requirements>
uv run ruff check .
uv run ty check .
uv run pytest
npm run check
npm run build
```

Production-аудиты не содержат известных уязвимостей, все проверки проходят.

### Результат 2026-08-18

Dependency fixes выполнены:

- React Router family: `8.2.0` -> `8.3.0`;
- `cryptography`: `49.0.0` -> `50.0.0`;
- `Pillow`: `12.2.0` -> `12.3.0`;
- `pydantic-settings`: `2.14.1` -> `2.14.2`;
- уязвимые transitive frontend build/test dependencies обновлены в lock-файле.

Проверки:

- полный `npm audit`: 0 vulnerabilities;
- production `pip-audit`: no known vulnerabilities;
- `npm ci`: passed;
- frontend format, lint, styles, API contract и typecheck: passed;
- frontend tests: 569 passed;
- frontend production build: passed;
- backend tests: 1008 passed, 34 PostgreSQL tests skipped без
  `BOOKER_TEE_TEST_DATABASE_URL`.

Exit gate этапа закрыт. Неиспользуемый и устаревший
`src/app/features/debts/mappers.py` удалён: его runtime consumers отсутствовали,
а актуальный mapping уже принадлежит `DebtReader`. После удаления `ruff`, `ty`,
backend tests и оба dependency audit прошли.

## 2. Включить регистрацию только по приглашениям

Статус: завершено 18 августа 2026 года.

Добавить явный режим регистрации:

```env
BOOKER_TEE_REGISTRATION_MODE=closed|invite_only|open
```

Production использует:

```env
BOOKER_TEE_REGISTRATION_MODE=invite_only
BOOKER_TEE_IDENTITY_EMAIL_ENABLED=true
```

Минимальная реализация переиспользует существующие workspace invitations:

1. Signup принимает invitation token.
2. Backend проверяет статус, срок действия и email приглашения.
3. Без действительного токена создание пользователя запрещено.
4. Регистрация не создаёт membership автоматически: приглашение принимает
   существующий authenticated accept-flow.
5. Публичные ошибки не раскрывают наличие пользователя или приглашения.
6. Сохраняются email verification и существующий auth rate limiting.

Exit gate:

- без приглашения аккаунт создать невозможно;
- просроченное или использованное приглашение отклоняется;
- email signup должен совпадать с email приглашения;
- полный signup -> verification -> invitation acceptance проходит;
- конкурентное или повторное принятие не создаёт дубли.

Реализовано без новой таблицы и без отдельной системы registration codes:

- `open`, `invite_only` и `closed` доступны через
  `BOOKER_TEE_REGISTRATION_MODE`;
- signup получает отдельный invitation token и не доверяет маршруту `next`;
- backend проверяет pending-статус, срок, активность workspace и точное
  совпадение нормализованного email;
- приглашение остаётся pending до существующего authenticated accept-flow;
- повторное verification-письмо сохраняет безопасный маршрут возврата;
- публичный отказ не раскрывает email или состояние приглашения.

Проверки этапа:

- backend security/API/application tests: 47 passed;
- PostgreSQL identity flow, включая реальный invite-only signup: 6 passed;
- полный backend suite: 1010 passed, 35 PostgreSQL tests skipped без
  общей test database;
- frontend invite/auth tests: 12 passed;
- полный frontend suite: 570 passed;
- Ruff, ty, ESLint, TypeScript и OpenAPI contract: passed;
- frontend production build: passed.

Exit gate этапа закрыт. Временная PostgreSQL test database после проверки
удалена.

## 3. Подготовить Telegram webhook

Статус: завершено 18 августа 2026 года.

Production использует:

```env
BOOKER_TEE_CHAT_INTEGRATIONS_ENABLED=true
BOOKER_TEE_TELEGRAM_MODE=webhook
BOOKER_TEE_TELEGRAM_WEBHOOK_SECRET=<random-secret>
```

Работы:

1. Оставить обязательную проверку
   `X-Telegram-Bot-Api-Secret-Token`.
2. Проверить, что непривязанный Telegram user не получает доступ к данным.
3. Проверить идемпотентность повторно доставленного update.
4. Применять те же upload/parser limits, что и для web upload.
5. Не логировать bot token, webhook secret, документы и финансовые реквизиты.

Exit gate:

- webhook с неверным или отсутствующим секретом отклоняется;
- корректный update проходит через существующий `ChatEventService`;
- повторная доставка не создаёт повторные финансовые записи;
- Telegram upload сохраняет document и parse attempt даже при ошибке парсера.

Telegram передаёт настроенный `secret_token` в заголовке webhook: [Bot API
setWebhook](https://core.telegram.org/bots/api#setwebhook).

Реализовано:

- secret header сравнивается через `secrets.compare_digest` до обработки update;
- production runtime требует Telegram-compatible secret длиной 32-256 символов;
- migration `20260818_0031` добавляет ID-only inbox
  `telegram_webhook_updates`, без raw provider payload;
- concurrent update получает единственного processing owner, completed update
  не обрабатывается повторно, failed update можно повторить;
- отсутствие или неверный secret и некорректный `update_id` отклоняются;
- предварительная проверка Telegram-файла использует общий
  `BOOKER_TEE_STATEMENT_UPLOAD_MAX_BYTES`;
- Telegram upload передаёт стабильный conversation-state ID в существующий
  idempotent statement upload flow;
- Compose передаёт Telegram, public URL и upload-limit settings приложению;
- webhook регистрируется командой
  `uv run python -m app.features.chat_integrations.webhook` без вывода секретов.

Проверки этапа:

- webhook/identity/upload/application tests: passed;
- реальный PostgreSQL concurrent claim, completed replay и failed retry: passed;
- migration upgrade, downgrade и повторный upgrade на чистой PostgreSQL: passed;
- полный backend suite: 1023 passed, 36 PostgreSQL tests skipped без общей
  test database;
- Ruff, ty, migration formatting и `docker compose config -q`: passed.

Exit gate этапа закрыт. Изолированная PostgreSQL test database после проверки
удалена.

## 4. Создать production image и Compose

Текущий `compose.yaml` предназначен для разработки: он публикует PostgreSQL и
FastAPI, монтирует исходники и запускает Uvicorn с `--reload`. Для production
нужен отдельный `compose.production.yaml`.

Требования:

1. Использовать собранный immutable application image.
2. Не монтировать исходники и не запускать `uv sync` при старте.
3. Не использовать `--reload`.
4. Не публиковать PostgreSQL на host network.
5. Не публиковать FastAPI на host network; разрешить доступ только Nginx в
   private Compose network.
6. Хранить PostgreSQL и uploads в persistent volumes.
7. Запускать application container не от `root`.
8. Добавить healthcheck и ограниченную ротацию логов.
9. Запускать `alembic upgrade head` отдельной одноразовой release-командой,
   а не при каждом старте приложения.

Exit gate:

- после пересоздания контейнеров база и документы сохраняются;
- порты PostgreSQL и FastAPI недоступны снаружи;
- application image запускается без исходников и development dependencies;
- неуспешная миграция не запускает новую версию приложения.

Статус: выполнено 18 августа 2026 года.

Реализовано:

- `Dockerfile` собирает React и FastAPI в один image и запускает приложение от
  непривилегированного пользователя `app` с UID/GID `10001`;
- `compose.production.yaml` не монтирует исходники, не запускает development
  frontend, `uv sync`, Alembic или Uvicorn `--reload` при старте;
- PostgreSQL и FastAPI доступны только в разделённых private Compose networks;
- PostgreSQL data и uploads хранятся в отдельных named volumes;
- app и PostgreSQL имеют healthchecks, restart policy и bounded Docker logs;
- секреты читаются из внешнего файла, путь к которому передаётся через
  `BOOKER_TEE_ENV_FILE`.

Release-последовательность:

```bash
export BOOKER_TEE_ENV_FILE=/etc/booker-tee/booker-tee.env
export BOOKER_TEE_IMAGE=booker-tee:$(git rev-parse --short HEAD)

docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml build app nginx
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  run --rm app alembic upgrade head && \
  docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml up -d
```

Оператор запускает новую версию только через `&&`: при ошибке Alembic команда
`up -d` не выполняется. Регистрацию Telegram webhook следует запускать отдельной
release-командой после успешного старта приложения.

Проверки этапа:

- production Compose config: passed;
- production image build и React build: passed;
- runtime user, отсутствие tests/dev dependencies и наличие SPA: passed;
- migration до `20260818_0031 (head)` отдельным one-off container: passed;
- healthcheck и private-network-only FastAPI binding: passed;
- PostgreSQL без published port: passed;
- PostgreSQL и uploads сохранились после `--force-recreate`: passed.

Exit gate этапа закрыт.

## 5. Настроить Nginx и TLS

Nginx работает как единственная публичная точка входа.

Требования:

1. Открыть `80/443`; HTTP перенаправлять на HTTPS.
2. Получить и автоматически обновлять сертификат Let's Encrypt.
3. Проксировать запросы на `app:8000` внутри private Compose network.
4. Передавать `Host`, `X-Forwarded-For` и `X-Forwarded-Proto`.
5. Uvicorn должен доверять forwarded headers только адресу Nginx, не `*`.
6. Ограничить частоту запросов к auth endpoints и Telegram webhook.
7. Использовать отдельные body limits:
   - около `25m` для document upload с multipart overhead;
   - `1m` для Telegram webhook и обычных запросов.
8. Настроить bounded connect/read/send timeouts.
9. Не логировать request body и секретные заголовки.
10. Закрыть снаружи `/health/db`, `/docs`, `/redoc` и `/openapi.json`.

Exit gate:

- HTTP всегда перенаправляется на HTTPS;
- сертификат валиден и renewal проверен в dry-run;
- Host validation и secure cookie работают за proxy;
- auth/webhook rate limits возвращают `429`;
- внутренние endpoints и upstream port недоступны из интернета.

Справочные документы:

- [FastAPI behind a proxy](https://fastapi.tiangolo.com/advanced/behind-a-proxy/);
- [Nginx proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html);
- [Nginx request rate limiting](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html).

Статус: repository-часть выполнена 18 августа 2026 года. Выпуск настоящего
сертификата и renewal dry-run ожидают домен, DNS и VPS.

Реализовано:

- Nginx `1.28.3-alpine` собирается как отдельный immutable image и является
  единственным сервисом с published ports `80/443`;
- FastAPI не имеет host-порта, а PostgreSQL и app разделены на proxy и internal
  database networks;
- Nginx передаёт canonical `Host`, `X-Forwarded-For` и `X-Forwarded-Proto`;
- Uvicorn доверяет только настраиваемой proxy CIDR, а не `*`;
- неизвестный Host отклоняется приложением;
- HTTP перенаправляется на canonical HTTPS URL;
- `/health/db`, `/docs`, `/redoc` и `/openapi.json` возвращают `404`;
- auth и Telegram webhook используют отдельные rate-limit zones с ответом
  `429`;
- общий body limit равен `1m`, а upload endpoint получает `25m`;
- connect/send/read timeouts ограничены, request body и секретные заголовки не
  добавлены в access log;
- Certbot `5.7.0` работает как one-off service с persistent certificate и ACME
  webroot volumes;
- `docker/renew-certificates.sh` выполняет renewal и reload Nginx; его следует
  запускать ежедневно из cron или systemd timer.

Первичный выпуск сертификата выполняется до запуска Nginx, когда DNS уже
указывает на VPS и порт `80` свободен:

```bash
export BOOKER_TEE_ENV_FILE=/etc/booker-tee/booker-tee.env

docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  run --rm --service-ports certbot
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml up -d
```

Проверка renewal после запуска Nginx:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  run --rm certbot renew --dry-run --webroot --webroot-path /var/www/certbot
```

Пример ежедневного cron на VPS:

```cron
17 3 * * * cd /opt/booker-tee && BOOKER_TEE_ENV_FILE=/etc/booker-tee/booker-tee.env ./docker/renew-certificates.sh
```

Локальные проверки этапа:

- production Compose config и `nginx -t`: passed;
- HTTP `301`, HTTPS proxy health и container healthchecks: passed;
- invalid Host: `400`;
- internal endpoints: `404`;
- обычный body размером 2 MiB: `413`, upload body: passed through Nginx;
- auth и Telegram webhook rate limits: `429`;
- FastAPI и PostgreSQL без published ports: passed;
- trusted forwarded client address через ограниченную proxy CIDR: passed;
- закреплённый Certbot image и one-off service: passed.

Внешний exit gate остаётся открытым только для валидного Let's Encrypt
сертификата и успешного renewal dry-run на реальном домене.

## 6. Настроить production environment и VPS

Обязательный baseline:

```env
BOOKER_TEE_ENVIRONMENT=production
BOOKER_TEE_DEBUG=false
BOOKER_TEE_SESSION_COOKIE_SECURE=true
BOOKER_TEE_ALLOWED_HOSTS=finance.example.com
BOOKER_TEE_PUBLIC_BASE_URL=https://finance.example.com
BOOKER_TEE_SECURITY_HEADERS_ENABLED=true
```

Секреты:

- использовать отдельные случайные значения для PostgreSQL, auth signing,
  Telegram bot, Telegram webhook и SMTP;
- хранить production env вне Git с правами `600`;
- не добавлять env или секреты в application image и логи;
- описать ротацию auth secret и Telegram token.

VPS:

- SSH только по ключам;
- отключить password login и root login;
- разрешить снаружи только `80/443`, а `22` по возможности ограничить trusted IP;
- не открывать `5432`, `8000` и `5173`;
- включить автоматические security updates;
- настроить ротацию логов и alert по заполнению диска.

После проверки React добавить Content Security Policy без `unsafe-inline`, если
текущий production build её допускает.

## 7. Настроить backup и restore

Один backup set должен включать:

- PostgreSQL dump;
- upload storage;
- manifest с временем, версиями приложения и миграции.

Минимальная безопасная процедура первого релиза:

1. Включить maintenance/остановить application container.
2. Выполнить `pg_dump` в custom format.
3. Архивировать upload storage.
4. Зашифровать и скопировать backup вне VPS.
5. Запустить приложение и проверить health.

Retention baseline:

- 7 ежедневных копий;
- 4 еженедельные копии;
- ежемесячный restore-test;
- целевые RPO 24 часа и RTO 2 часа.

Exit gate: PostgreSQL и документы успешно восстанавливаются на чистом окружении,
после чего проходят login, открытие документа и проверка ledger balance.

Справка: [PostgreSQL Backup and
Restore](https://www.postgresql.org/docs/16/backup.html).

## 8. Провести production-like репетицию

На тестовом домене выполнить:

1. HTTPS и HTTP redirect.
2. Invite-only signup, email verification и password recovery.
3. Login/logout, CSRF, session refresh и session revocation.
4. Workspace isolation для read и mutation endpoints.
5. PDF/XLSX upload, review и confirmation.
6. Повторный import без двойного учёта.
7. Telegram binding, webhook и document upload.
8. Перезапуск контейнеров без потери данных.
9. Полный backup -> clean restore -> smoke test.
10. Dependency audit и container image scan.

Exit gate: все проверки задокументированы и повторяемы одной release
инструкцией; blocker/high findings отсутствуют.

## 9. Выполнить первый production release

Порядок:

```text
backup
  -> build and scan image
  -> start PostgreSQL
  -> alembic upgrade head
  -> start FastAPI
  -> internal health check
  -> enable Nginx and TLS
  -> set Telegram webhook with secret_token
  -> production smoke test
  -> invite first users
```

Rollback:

- сохранять предыдущий application image;
- откатывать код только при обратно совместимой схеме;
- не выполнять автоматический Alembic downgrade;
- при несовместимой миграции использовать заранее проверенный backup/restore.

## 10. Поддерживать после запуска

- ежедневно проверять успешность backup;
- мониторить availability, ошибки `5xx`, rate-limit rejects, disk и certificate
  expiry;
- не отправлять raw financial data и документы во внешние monitoring services;
- повторять dependency и image audit перед каждым релизом;
- применять security updates ОС и base images;
- периодически проверять восстановление и отзыв Telegram/session credentials.

## Порядок исполнения

```text
1. Dependency fixes
2. Invite-only registration
3. Telegram webhook hardening
4. Production image and Compose
5. Nginx and TLS
6. VPS and secrets
7. Backup and restore test
8. Production-like rehearsal
9. First release
10. Ongoing operations
```

Публичный доступ не открывается до завершения этапов 1–8.
