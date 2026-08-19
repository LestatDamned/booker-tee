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
  -> temporary upload storage (persistent volume, retention-controlled)
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
6. Хранить PostgreSQL и временные uploads в разных persistent volumes;
   originals удаляются по retention policy и не являются backup-данными.
7. Запускать application container не от `root`.
8. Добавить healthcheck и ограниченную ротацию логов.
9. Запускать `alembic upgrade head` отдельной одноразовой release-командой,
   а не при каждом старте приложения.

Exit gate:

- после пересоздания контейнеров база и ещё не удалённые временные originals
  сохраняются;
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
- PostgreSQL data и временные uploads хранятся в отдельных named volumes;
- app и PostgreSQL имеют healthchecks, restart policy и bounded Docker logs;
- секреты читаются из внешнего файла, путь к которому передаётся через
  `BOOKER_TEE_ENV_FILE`.

Release-последовательность:

```bash
export BOOKER_TEE_ENV_FILE=/etc/booker-tee/booker-tee.env
export BOOKER_TEE_IMAGE=booker-tee:$(git rev-parse --short HEAD)

docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml build app nginx
./scripts/production-preflight.sh && \
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
- PostgreSQL и ещё не истёкшие uploads сохранились после `--force-recreate`:
  passed.

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

## 6. Закрыть pre-VPS блокеры

Этап выполняется локально до покупки или подготовки VPS.

### 6.1. Защитить bearer tokens и access logs

Email verification, password reset, email change и workspace invitation tokens
не должны попадать в URL, `Referer`, Nginx/Uvicorn access logs или error logs.

Работы:

1. Передавать email tokens через URL fragment и очищать fragment сразу после
   чтения React-приложением.
2. Убрать invitation token из path/query и передавать его API в request body.
3. Использовать безопасный Nginx log format без query string и `Referer`.
4. Отключить дублирующий Uvicorn access log в production.
5. Не логировать raw token даже при validation, proxy и parser errors.

Exit gate:

- уникальный marker-token не появляется в Nginx, Uvicorn и application logs;
- verification, reset, email change, invitation preview и accept работают;
- token удаляется из browser address bar до дальнейших запросов;
- token остаётся одноразовым и ограниченным по времени.

Справка:

- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html);
- [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html).

Статус: выполнено 18 августа 2026 года.

Реализовано:

- verification, password reset и email change links передают token через URL
  fragment; React читает его один раз и сразу очищает browser address bar;
- workspace invitation использует `/app/workspaces/invitation#token=...`, а
  preview и accept принимают token только в JSON body стабильных POST endpoints;
- invitation сохраняется во fragment при переходах через login/signup и не
  попадает во вложенный `next` query;
- Nginx server blocks переопределяют стандартный `combined` log безопасным
  форматом с методом и `$uri`, но без query, Referer, request body и secret
  headers;
- production Uvicorn запускается с `--no-access-log`;
- OpenAPI contract, generated TypeScript и runtime-документация обновлены.

Проверки этапа:

- реальный Nginx marker-запрос: в access/error output есть только
  `GET /auth/verify`, marker-token отсутствует;
- production Compose config, Nginx image build и `nginx -t`: passed;
- backend: Ruff и ty passed, `1024 passed`, `36 skipped` без test PostgreSQL;
- frontend: format, lint, styles, API contract, typecheck, `572 passed` и
  production build — passed.

Exit gate этапа 6.1 закрыт.

### 6.2. Ограничить ресурсы PDF/XLSX parser

Upload byte limit недостаточен: небольшой PDF или сжатый XLSX может содержать
слишком много страниц, sheets, rows или cells.

Работы:

1. Добавить документированные configurable limits для PDF pages и XLSX
   sheets/rows/columns/cells.
2. Отклонять подозрительно большой распакованный XLSX до полной обработки.
3. Выполнять синхронный extraction вне async event loop.
4. Ограничить memory, CPU и PIDs application container.
5. При limit/error сохранять uploaded document, raw metadata и failed parse
   attempt без частичного ledger posting.

Exit gate:

- oversized PDF/XLSX завершается контролируемой review/error state;
- `/health` остаётся отзывчивым во время допустимого parse;
- превышение лимита не подтверждает операции и не теряет исходный документ;
- web upload и Telegram используют одинаковые ограничения.

Статус на 18 августа 2026 года: выполнено.

Реализовано:

- общий для web upload и Telegram набор configurable limits: PDF pages, XLSX
  sheets, rows, columns, total cells и uncompressed archive size;
- синхронный PDF/XLSX extraction вынесен из async event loop в worker thread;
- превышение лимита проходит через существующий failed parse flow: исходный файл
  и документ сохраняются, parse attempt завершается ошибкой, ledger posting не
  запускается;
- application container ограничен по CPU, memory и PIDs; значения вынесены в
  production env с безопасными defaults;
- лимиты и параметры контейнера документированы в `.env.example`.

Проверки:

- resource-limit, web upload и Telegram upload tests: `35 passed`;
- полный backend suite: `1032 passed`, `36 skipped` без test PostgreSQL;
- Ruff, ty и production Compose config: passed.

Exit gate этапа 6.2 закрыт.

### 6.2.1. Защитить originals и ограничить retention 48 часами

Оригинальный PDF/XLSX нужен только до надёжного сохранения результата parse.
После этого финансовый audit опирается на document metadata, SHA-256, raw
extraction, raw transactions, parse attempts и confirmed ledger records в
PostgreSQL. Долгое хранение source file увеличивает ущерб при утечке и не даёт
текущему приложению дополнительной функции.

Политика:

- после успешного commit распознанной или автоматически mapped выписки удалять
  original сразу;
- неизвестную выписку со `StoredValidationReport.status == "needs_mapping"`
  хранить до 48 часов с момента upload, даже если extraction успешно сохранил
  raw tables; это окно позволяет проверить и исправить ручной mapping;
- при failed/incomplete parse также хранить original не более 48 часов, после
  чего пользователь при необходимости загружает выписку заново;
- 48 часов — верхняя граница и аварийная страховка, а не обязательный срок
  хранения каждого файла;
- document record, SHA-256, raw extraction, raw transactions и ledger records
  retention cleanup не удаляет;
- originals не входят в долгосрочные backups.

Работы:

1. Добавить `BOOKER_TEE_UPLOAD_RETENTION_HOURS=48`, nullable `storage_key` и
   `source_file_deleted_at`; после удаления очищать storage key и записывать
   timestamp без удаления `UploadedDocument`.
2. Хранить файл под сгенерированным application именем без original filename;
   original filename оставлять только в авторизованном document metadata.
3. Создавать upload directories с mode `0700`, файлы с mode `0600`, запрещать
   overwrite и проверять, что resolved path находится внутри upload root.
4. Проверять не только extension и недоверенный Content-Type, но также PDF/XLSX
   file signature и ожидаемую XLSX ZIP structure до parser processing.
5. После успешного parse commit удалять source file, кроме документа с
   `needs_mapping`. Для него cleanup использует обычный 48-hour cutoff даже
   после завершения ручного mapping. Ошибка удаления не откатывает сохранённый
   parse: файл подхватывает idempotent retention cleanup.
6. Добавить одну CLI-команду без отдельного scheduler dependency. Она каждый
   час небольшими batches удаляет expired originals, чистит orphan files и
   согласует DB metadata с отсутствующими файлами. Сначала удаляется файл,
   затем фиксируется `source_file_deleted_at`; повторный запуск безопасен.
7. Не выводить в cleanup logs filename, storage key, содержимое или financial
   metadata: только counts, итоговый статус и безопасный error category.
8. Сделать root filesystem application container read-only, дать bounded
   `tmpfs` для `/tmp`, сбросить Linux capabilities и включить
   `no-new-privileges`; upload volume остаётся единственным постоянным writable
   filesystem приложения.
9. После завершения Telegram upload очищать из conversation state `file_id`,
   `file_unique_id`, filename и MIME metadata; то же делать для expired upload
   states.
10. После Telegram upload показывать сообщение:

    > Выписка загружена. Исходный файл на сервере Booker Tee удаляется сразу
    > после успешной автоматической обработки. Если выписке нужен ручной
    > маппинг или обработка не завершилась, файл автоматически удаляется через
    > 48 часов. Для дополнительной конфиденциальности удалите сообщение с
    > файлом из этого чата. Telegram хранит свою копию отдельно от Booker Tee.

    Первый increment только уведомляет пользователя и не удаляет Telegram
    message автоматически.

11. Исключить upload volume из долгосрочного backup. После восстановления
    PostgreSQL запускать reconciliation той же CLI-командой: отсутствующие
    originals отмечаются удалёнными, а parsed/raw/ledger data остаются доступны.

Прогресс на 19 августа 2026 года:

- пункт 1 выполнен: добавлены `BOOKER_TEE_UPLOAD_RETENTION_HOURS=48`, nullable
  `UploadedDocument.storage_key` и `source_file_deleted_at`;
- пункты 2-4 выполнены: original filename больше не участвует в storage key,
  directories/files создаются с `0700/0600`, overwrite запрещён, resolved path
  ограничен upload root, PDF/XLSX проходят signature/ZIP structure validation;
- migration `20260819_0032` проверена полным upgrade, downgrade с уже очищенным
  storage key и повторным upgrade на PostgreSQL;
- удаление document уже безопасно обрабатывает отсутствующий source file;
- пункт 5 выполнен: после commit распознанного или автоматически mapped parse
  source удаляется, а `storage_key=NULL` и `source_file_deleted_at` фиксируются
  отдельным commit; `needs_mapping`, failed и incomplete сохраняются для
  retention cleanup;
- filesystem error не отменяет committed parse и логируется без path/filename;
- пункты 6-7 выполнены: команда
  `uv run python -m app.features.imports.documents.source_cleanup` небольшими
  DB batches удаляет originals старше 48 часов, согласует отсутствующие файлы,
  удаляет один bounded batch старых orphan files и безопасна для повторного
  запуска;
- команда выводит только итоговый status и counts, логирует только тип ошибки и
  возвращает ненулевой exit code при частичном сбое;
- почасовой systemd timer для этой команды будет добавлен при подготовке VPS;
- пункт 8 выполнен: root filesystem application container работает read-only,
  `/tmp` предоставляется как `tmpfs` с лимитом 128 MiB и флагами
  `noexec,nosuid,nodev`, все Linux capabilities сброшены, повышение привилегий
  запрещено через `no-new-privileges`; upload volume остаётся единственным
  постоянным writable filesystem приложения;
- пункты 9-10 выполнены: после успешного Telegram upload conversation state
  очищается от file identifiers и metadata; consumed и expired upload states
  согласуются почасовой cleanup-командой, а бот объясняет 48-часовую retention
  policy и предлагает удалить исходное сообщение с файлом из Telegram;
- пункт 11 ещё не реализован.

Exit gate:

- original распознанной или автоматически mapped выписки отсутствует после
  parse commit, а document, raw data и операции доступны;
- original с `needs_mapping` доступен cleanup-процессу до 48-hour cutoff; после
  удаления ручной mapping продолжает работать с raw tables из PostgreSQL;
- failed, abandoned и orphan uploads старше 48 часов удаляются почасовой
  idempotent командой;
- cleanup crash между file deletion и DB update исправляется повторным запуском;
- новые файлы и каталоги имеют `0600/0700`, user filename не участвует в
  filesystem path;
- Nginx и browser API не получают upload volume или storage key;
- production backup/restore не содержит originals и корректно reconciles их
  отсутствие;
- Telegram file metadata очищается, а пользователь получает privacy notice;
- web и Telegram uploads проходят одинаковую signature, parser и retention
  policy.

Не включать в первый increment ClamAV sidecar, file download endpoint,
application-level file encryption, отдельный queue или scheduler. Вернуться к
anti-malware scanning при расширении регистрации, появлении file sharing или
измеренном риске, который не покрывают allowlist, signature validation,
resource limits и container isolation.

Справка:

- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html);
- [Telegram Bot API deleteMessage](https://core.telegram.org/bots/api#deletemessage);
- [Telegram Privacy Policy: Cloud Chats](https://telegram.org/privacy#3-3-1-cloud-chats).

### 6.3. Добавить bootstrap первого owner

При `invite_only` первый пользователь не может получить приглашение от ещё не
существующего owner.

Нужна одноразовая CLI-команда без публичного HTTP endpoint:

1. Получить email/name и пароль через скрытый interactive input.
2. Атомарно создать verified user, personal workspace и owner membership.
3. Отказаться перезаписывать существующего пользователя или повторно создавать
   bootstrap owner.
4. Не выводить пароль, token или password hash в stdout/logs.

Exit gate:

- команда работает через one-off application container;
- повторный запуск безопасно отклоняется;
- bootstrap owner входит в приложение и создаёт первое приглашение;
- публичная регистрация всё время остаётся `invite_only`.

Статус: выполнено 19 августа 2026 года.

Команда запускается интерактивно после применения migrations:

```bash
docker compose --env-file "$BOOKER_TEE_ENV_FILE" -f compose.production.yaml \
  run --rm app python -m app.features.users.bootstrap
```

Она использует скрытый ввод и подтверждение пароля, блокирует конкурентное
создание пользователей на время транзакции, создаёт verified user, personal
workspace, owner membership и audit event одним commit. Если в базе уже есть
хотя бы один пользователь, bootstrap безопасно завершается с ошибкой.

### 6.4. Добавить production preflight

Deployment-specific preflight должен завершаться до migration/start и не
выводить значения секретов.

Он проверяет:

- `DEBUG=false`, security headers включены, registration mode равен
  `invite_only`;
- cookie secure, canonical domain, allowed hosts и HTTPS public URL согласованы;
- identity email и SMTP STARTTLS включены, обязательные SMTP поля заполнены;
- Telegram работает в webhook mode с bot token и сильным webhook secret;
- auth, PostgreSQL, Telegram и SMTP secrets не используют defaults и не
  совпадают друг с другом;
- `DATABASE_URL` использует Compose host `postgres`;
- production env отсутствует в Git и имеет права `600` на сервере.

Exit gate: одна preflight-команда принимает корректный sanitized test env и
отклоняет каждую небезопасную конфигурацию отдельным понятным сообщением.

Статус: выполнено 19 августа 2026 года.

После сборки production image и до migrations оператор запускает:

```bash
export BOOKER_TEE_ENV_FILE=/etc/booker-tee/booker-tee.env
./scripts/production-preflight.sh
```

Host wrapper отклоняет отсутствующий, отслеживаемый Git или доступный шире
`0600` env-файл. Затем one-off application container проверяет production mode,
debug/registration/security settings, согласованность domain/allowed hosts/HTTPS
URL, SMTP STARTTLS и обязательные email/Telegram параметры, Compose database
host, placeholder/короткие/совпадающие secrets. Вывод содержит только названия
переменных и причины; подключения к SMTP и Telegram не выполняются.

## 7. Добавить strict Content Security Policy

React SPA build содержит inline bootstrap scripts, поэтому `script-src 'self'`
без подготовки сломает приложение.

Статус: завершено 19 августа 2026 года. FastAPI один раз при старте читает
immutable `index.html`, вычисляет SHA-256 каждого inline script и разрешает эти
хэши вместе с same-origin assets. Enforced `Content-Security-Policy` применяется
только к SPA HTML; API и static asset responses не получают CSP.

Browser validation 19 августа 2026 года:

- login проверен в desktop/tablet/mobile без CSP console errors;
- authenticated operations, reports и upload дали 9 ответов `200`, без console
  errors, page errors и failed requests;
- реальный XLSX прошёл upload, mapping и import review; целевой desktop review
  audit завершился без CSP или runtime ошибок;
- audit использует канонический `/app/operations` и поддерживает точечный выбор
  `--viewport`, чтобы stateful security gate не зависел от полного visual audit.

После включения enforced CSP негативная Playwright-проверка подтвердила, что
React login загружается, а неизвестный inline script и внешний cross-origin
script не выполняются и не отправляют запрос. Проверка запускается командой
`uv run python scripts/ui_audit.py --check-csp`.

Работы:

1. Генерировать SHA-256 hashes inline scripts из того же immutable build,
   который попадает в application image.
2. Сначала проверить политику через `Content-Security-Policy-Report-Only`.
3. После browser tests включить enforced CSP без `unsafe-inline` и
   `unsafe-eval`.
4. Ограничить как минимум `default-src`, `script-src`, `style-src`, `img-src`,
   `connect-src`, `object-src`, `base-uri` и `frame-ancestors`.

Exit gate:

- login, invitation, upload, review и reports работают с enforced CSP;
- browser console не содержит CSP violations;
- неизвестный inline/external script блокируется;
- CSP hashes обновляются только вместе с соответствующим frontend build.

Справка: [MDN Content Security
Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP).

## 8. Реализовать и проверить backup/restore локально

Статус: выполняется. Первый increment добавляет `scripts/backup.sh`: приложение
останавливается на время согласованного `pg_dump -Fc` и гарантированно
запускается обратно; новый приватный backup-каталог получает dump, manifest и
SHA-256 checksums. Upload volume и временные originals не читаются и не
архивируются.

Один backup set должен включать:

- PostgreSQL custom-format dump;
- manifest с временем, application image, Alembic revision, checksums и явной
  отметкой, что временные originals исключены.

Upload storage archive в backup не входит: originals являются временными
данными с максимальным retention 48 часов. Их долгосрочная копия нарушила бы
эту политику.

Минимальная безопасная процедура:

1. Остановить application mutations на время согласованного backup set.
2. Выполнить `pg_dump -Fc` из совместимой PostgreSQL image.
3. Сформировать manifest и SHA-256 checksums без upload volume.
4. Восстановить dump в чистый PostgreSQL volume и создать пустой upload volume.
5. Выполнить upload reconciliation: отсутствующие originals отметить удалёнными
   без удаления document/raw/ledger data.
6. Выполнить login, открытие документа, import review и проверку ledger balance.

Retention baseline после появления VPS:

- 7 ежедневных копий;
- 4 еженедельные копии;
- ежемесячный restore-test;
- целевые RPO 24 часа и RTO 2 часа.

Exit gate: repeatable backup/restore commands восстанавливают sanitized
production-like PostgreSQL dataset на чистом Compose project; originals
ожидаемо отсутствуют, а document/raw/ledger workflows продолжают работать.

Справка: [PostgreSQL Backup and
Restore](https://www.postgresql.org/docs/16/backup.html).

## 9. Автоматизировать release gate и clean-room rehearsal

Release gate должен выполняться локально и в выбранной CI-системе:

1. Backend Ruff, ty и полный pytest с PostgreSQL.
2. Frontend format, lint, styles, typecheck, tests и production build.
3. Python/npm production dependency audits.
4. Production Compose config, app/Nginx image build и migration на чистой БД.
5. Container vulnerability scan без blocker/high findings.
6. SBOM и provenance для публикуемых immutable images.
7. Clean-room flow: bootstrap owner -> invite -> login -> PDF/XLSX import ->
   Telegram replay -> source cleanup -> restart -> backup без originals -> clean
   restore -> reconciliation -> smoke test.
8. Проверить rollback к предыдущему application image без Alembic downgrade.

Exit gate: проверки повторяемы одной release-инструкцией; ручной release не
может обойти migration, audit, backup и smoke-test gates незаметно.

Справка: [Docker build
attestations](https://docs.docker.com/build/metadata/attestations/).

## 10. Настроить production environment и VPS

Обязательный baseline:

```env
BOOKER_TEE_ENVIRONMENT=production
BOOKER_TEE_DEBUG=false
BOOKER_TEE_DOMAIN=finance.example.com
BOOKER_TEE_CERTBOT_EMAIL=admin@example.com
BOOKER_TEE_REGISTRATION_MODE=invite_only
BOOKER_TEE_IDENTITY_EMAIL_ENABLED=true
BOOKER_TEE_SMTP_STARTTLS=true
BOOKER_TEE_SESSION_COOKIE_SECURE=true
BOOKER_TEE_ALLOWED_HOSTS=finance.example.com
BOOKER_TEE_PUBLIC_BASE_URL=https://finance.example.com
BOOKER_TEE_SECURITY_HEADERS_ENABLED=true
BOOKER_TEE_CHAT_INTEGRATIONS_ENABLED=true
BOOKER_TEE_TELEGRAM_MODE=webhook
BOOKER_TEE_UPLOAD_RETENTION_HOURS=48
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
- включить синхронизацию системного времени;
- настроить ротацию логов и alert по заполнению диска.

Дополнительно на VPS:

- зашифровать PostgreSQL backup и копировать его вне VPS; upload originals в
  backup не включать;
- установить расписание backup, hourly upload cleanup, certificate renewal и
  restore-test;
- настроить domain A/AAAA и необходимые SMTP SPF/DKIM/DMARC records;
- настроить alert по availability, `5xx`, certificate expiry и заполнению диска.

Exit gate:

- SSH и firewall baseline проверены с отдельной активной сессией;
- production preflight проходит с реальным env;
- настоящий Let's Encrypt certificate и renewal dry-run проходят;
- SMTP, Telegram webhook и encrypted offsite backup проверены с VPS.

## 11. Выполнить первый production release

Порядок:

```text
backup
  -> build and scan image
  -> start PostgreSQL
  -> alembic upgrade head
  -> start FastAPI
  -> internal health check
  -> bootstrap first owner
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

## 12. Поддерживать после запуска

- ежедневно проверять успешность backup;
- проверять успешность hourly upload cleanup и отсутствие expired/orphan files;
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
5. Containerized Nginx and TLS repository setup
6. Pre-VPS token/log/parser/upload-retention/bootstrap/preflight hardening
7. Strict CSP
8. Local backup and clean restore test
9. Automated release gate and clean-room rehearsal
10. VPS, secrets, real TLS and external integrations
11. First release
12. Ongoing operations
```

Публичный доступ не открывается до завершения этапов 1–10 и начала
контролируемого первого release.
