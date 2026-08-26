# Защита загрузки выписок для недоверенных пользователей

Статус: `READY`, план одобрен пользователем 2026-08-26.

## Цель

Сохранить синхронный web/Telegram workflow и review-first финансовую семантику,
но безопасно принимать специально подготовленные PDF/XLSX от недоверенных
авторизованных пользователей:

- parser hang, OOM или crash не останавливает API;
- parser не получает секреты, доступ к БД, сети и сохранённым выпискам;
- каждый созданный `ParseAttempt` получает терминальный статус при
  контролируемой ошибке;
- входные файлы и extraction result имеют жёсткие ограничения;
- массовые загрузки ограничены на edge и по фактической parser concurrency;
- retained sources очищаются по расписанию с наблюдаемыми ошибками.

Новый queue/backend/storage не вводится. Схема БД не меняется, Alembic
migration не нужна.

## Принятое решение

Parsing выполняется в отдельном hardened sidecar-контейнере, а не в FastAPI и
не в subprocess под UID приложения.

```text
FastAPI container                       Parser container
-----------------                       ----------------
DB credentials                          no secrets / no env_file
uploads volume                          no uploads volume
proxy + database networks               network_mode: none
        \                               /
         bounded stream through Unix socket
```

FastAPI передаёт один bounded-файл по Unix socket. Sidecar сохраняет только
текущий job во внутренний bounded `/tmp`, запускает для него отдельный
`exec`-worker и возвращает bounded JSON. Одновременно выполняется один job.

## Этап 1. Терминальное состояние attempt и active account

Изменить:

- `src/app/features/imports/documents/commands/upload.py`;
- `src/app/features/imports/documents/repository.py`;
- `src/app/features/imports/documents/attempts.py`;
- `src/app/features/ledger/application/ledger_reference_resolver.py`.

### Реализация

1. Сохранить существующие commits документа и `RUNNING` attempt до длительной
   обработки, чтобы не держать транзакцию во время parsing.
2. Оставить `StatementUploadUseCase` единственным владельцем транзакций.
3. Обработать ожидаемые ошибки, неожиданный `Exception` и отдельно
   `asyncio.CancelledError` после создания attempt:
   - остановить активный parser job;
   - откатить частичные raw rows, mapping и rule changes;
   - повторно загрузить document и attempt с workspace scope;
   - отметить attempt `FAILED`, document `FAILED_TO_PARSE`;
   - сохранить original source;
   - зафиксировать failure state отдельной явной транзакцией;
   - unexpected exception/cancellation повторно поднять после bounded cleanup.
4. Если extraction завершился, но completion упал, сохранить bounded
   `ExtractedStatement` в существующих raw JSON полях.
5. Не сохранять raw exception, filesystem path или содержимое документа в
   error/log.
6. Проверять `account.is_active` до debt/non-debt branching. Чужой и архивный
   счёт должны возвращать существующий `upload_account_not_found`.

Гарантия терминального статуса действует при доступной БД. SIGKILL, host loss
и DB outage относятся к operational recovery, а не маскируются как успешно
обработанная ошибка.

### Acceptance criteria

- extractor error, timeout, worker signal, parser/analyzer/mapping exception и
  контролируемая cancellation не оставляют attempt в `RUNNING`;
- частично созданные `RawTransaction` откатываются;
- bounded extracted raw сохраняется после completion failure;
- original source остаётся доступен для retry/review;
- unexpected failure возвращает 5xx только после записи failure state;
- confirmed operations не создаются;
- чужой и архивный account получают одинаковый безопасный ответ.

### Тесты

- расширить `tests/features/imports/test_imports.py`;
- расширить `tests/api/test_import_upload_api.py`;
- добавить PostgreSQL integration test для rollback частичных raw rows и
  committed failure state.

## Этап 2. Bounded PDF output

Изменить:

- `src/app/features/imports/parsers/extractors/limits.py`;
- `src/app/features/imports/parsers/extractors/pdf.py`;
- `src/app/core/settings.py`;
- `.env.example`.

### Начальные границы

- `BOOKER_TEE_STATEMENT_PDF_MAX_CHARACTERS=5000000`;
- `BOOKER_TEE_STATEMENT_PDF_MAX_TABLES=2000`;
- `BOOKER_TEE_STATEMENT_PDF_MAX_CELLS=500000`;
- `BOOKER_TEE_STATEMENT_EXTRACTION_RESULT_MAX_BYTES=67108864`;
- `BOOKER_TEE_STATEMENT_PARSER_WALL_TIMEOUT_SECONDS=60`;
- `BOOKER_TEE_STATEMENT_PARSER_CPU_SECONDS=45`;
- `BOOKER_TEE_STATEMENT_PARSER_MEMORY_BYTES=536870912`.

Все значения положительные; CPU limit не превышает wall timeout. Значения
калибруются только на sanitized production-like fixtures.

После каждой PDF page, до добавления результата:

- считать суммарные символы текста и non-`None` table cells;
- считать tables и cells;
- при превышении сразу поднимать `StatementResourceLimitError`;
- не сохранять частичный результат текущей страницы.

Page count остаётся первой дешёвой проверкой. Output limits защищают память
parent и JSONB; sidecar limits защищают от pathological page внутри
`pdfplumber` до момента подсчёта результата.

### Acceptance criteria и тесты

- превышение каждого лимита заканчивается `FAILED_TO_PARSE`;
- source сохраняется, raw fragment не попадает в error;
- лимиты применяются накопительно между страницами;
- exact boundary и обычные fixtures успешно обрабатываются;
- тесты покрывают overflow characters/tables/cells и multi-page accumulation.

## Этап 3. Hardened parser sidecar

Добавить:

- `src/app/features/imports/parsers/sidecar/client.py`;
- `src/app/features/imports/parsers/sidecar/server.py`;
- `src/app/features/imports/parsers/sidecar/worker.py`;
- `src/app/features/imports/parsers/sidecar/protocol.py`.

Изменить:

- `src/app/features/imports/documents/commands/upload.py`;
- `src/app/core/settings.py`;
- `.env.example`;
- `Dockerfile`;
- `compose.yaml`;
- `compose.production.yaml`.

### IPC protocol

Использовать Unix domain `SOCK_STREAM`, не HTTP/TCP:

1. Shared volume содержит только socket; parser не монтирует `uploads`.
2. App читает сохранённый source и отправляет его chunks через socket.
3. Малый length-prefixed header содержит только protocol version, расширение,
   declared byte count и numeric extraction limits.
4. Обе стороны независимо ограничивают header, фактически принятые bytes и
   response bytes.
5. Response — length-prefixed JSON envelope, который parent валидирует через
   Pydantic `ExtractedStatement`.
6. Storage path, workspace/account IDs, environment и secrets не передаются.
7. Не использовать `pickle`, shell invocation или динамический import из
   request data.

### Job lifecycle

1. Проверить protocol/version/header/extension/size.
2. Если job уже выполняется, вернуть bounded `busy`.
3. Записать stream в private `0600` file внутри sidecar `/tmp`.
4. Запустить `sys.executable -I -m ...worker` без shell.
5. До импорта `pdfplumber/openpyxl` применить `RLIMIT_AS`, `RLIMIT_CPU` и
   пониженный process priority.
6. Ограничить stdout; stderr направить в `DEVNULL`.
7. По wall timeout или disconnect выполнить `kill()` и `wait()`.
8. В `finally` удалить job file и освободить single-job slot.

### Container hardening

Parser service использует тот же immutable image, но:

- запускается под отдельным non-root UID;
- не получает `env_file` и секретные environment variables;
- использует `network_mode: none`;
- не монтирует uploads, Docker socket и app tmpfs;
- имеет read-only root filesystem;
- использует `cap_drop: [ALL]` и `no-new-privileges:true`;
- получает bounded `/tmp` с `noexec,nosuid,nodev`;
- имеет отдельные CPU, RAM и PID limits;
- получает restart policy;
- монтирует только IPC volume.

Child `RLIMIT_AS` должен быть ниже memory limit parser container. OOM/restart
parser-контейнера разрывает socket, но не включает API в тот же OOM scope.

Добавить `PING/PONG` healthcheck. На startup app ожидает healthy parser с
bounded timeout. Runtime outage переводится в typed
`ParserUnavailableError`, но app health и read API остаются доступными.

### Failure mapping

Sidecar timeout, OOM, disconnect, protocol error и invalid result:

- откатывают частичные completion writes;
- переводят attempt/document в failure state;
- сохраняют source;
- сохраняют только sanitized error code: `timeout`, `resource_limit`,
  `unavailable` или `invalid_result`.

Web и Telegram обязаны использовать один sidecar client.

### Acceptance criteria

- parser allocations принадлежат отдельному cgroup, не API;
- parser OOM/restart не перезапускает app container;
- hard wall/CPU/memory limits завершают job и освобождают slot;
- cancellation убивает worker;
- одновременно выполняется максимум один extraction job;
- request и response capped с обеих сторон;
- sidecar видит только текущий stream, а не retained uploads;
- sidecar не видит DB URL, auth/session, SMTP или Telegram secrets;
- sidecar не имеет маршрута к PostgreSQL, API или интернету;
- root filesystem read-only, capabilities отсутствуют;
- parser RCE ограничен текущим container/job и доступностью IPC.

### Тесты

Добавить:

- `tests/features/imports/test_parser_sidecar_protocol.py`;
- `tests/features/imports/test_parser_sidecar_client.py`;
- `tests/features/imports/test_parser_sidecar_server.py`;
- `tests/core/test_production_parser_service.py`.

Покрыть success PDF/XLSX, input/output overflow, malformed header, timeout,
memory/CPU kill, invalid JSON/schema, `busy`, disconnect, restart mapping и
`PING/PONG`. Compose test проверяет отсутствие networks, env file и uploads
mount, отдельный UID и все hardening/limit directives.

## Этап 4. Streaming Telegram download

Изменить:

- `src/app/features/chat_integrations/schemas.py`;
- `src/app/features/chat_integrations/providers/base.py`;
- `src/app/features/chat_integrations/providers/telegram_client.py`;
- `src/app/features/chat_integrations/application.py`.

### Реализация

1. Заменить `response.content -> bytes -> BytesIO` на
   `httpx.AsyncClient.stream`.
2. Считать фактические bytes по chunks и abort при превышении существующего
   `statement_upload_max_bytes`.
3. Писать в `tempfile.SpooledTemporaryFile(max_size=1 MiB, mode="w+b")`.
4. Передавать seeked file object в `UploadFile` и закрывать spool в `finally`.
5. Использовать Telegram `file_size` только как раннюю оптимизацию, не как
   security boundary.

### Acceptance criteria и тесты

- отсутствующий или ложный `file_size` не обходит 20 MiB hard cap;
- response не материализуется целиком в RAM;
- spool закрывается при success, oversize и exception;
- Telegram проходит через общий idempotency/account/sidecar workflow;
- тесты покрывают chunked success, exact boundary, one byte over, missing
  metadata и network exception.

## Этап 5. Nginx upload abuse limits

Изменить `docker/nginx/default.conf.template`:

- применить отдельные `limit_req_zone` и `limit_conn_zone` только к
  `POST /api/v1/imports/documents`;
- начальные значения: `6r/m`, `burst=3`, `nodelay`, максимум два соединения;
- сохранить `client_max_body_size 25m`;
- вернуть `429` без очереди долгих parser requests;
- использовать `$binary_remote_addr`, не сырой `X-Forwarded-For`.

Если перед Nginx появится CDN/LB, trusted real-IP CIDRs оформляются отдельным
deployment change. Per-workspace/distributed quotas добавляются только если
IP limiting и single-job sidecar окажутся недостаточными по метрикам.

Добавить `tests/core/test_nginx_upload_limits.py` и release smoke с реальными
последовательными и concurrent POST через Nginx.

## Этап 6. Hourly cleanup и наблюдаемые ошибки

Изменить:

- `compose.production.yaml`;
- `docs/deploy/plan/README.md`;
- `docs/COMMANDS.md`.

Добавить `upload-cleanup` service на существующем immutable image:

- запуск cleanup сразу после старта и затем ежечасно;
- non-zero exit завершает service process, Docker restart делает сбой видимым;
- uploads volume writable, доступ к database network;
- `read_only`, `cap_drop: ALL`, `no-new-privileges`;
- bounded CPU/RAM/PID и logging;
- никаких новых scheduler dependencies.

Runbook требует проверять container status/restart count, `partial_failure` и
свободное место uploads volume. Raw path/content не должны попадать в logs.

Расширить `tests/features/imports/test_source_cleanup.py` и добавить узкий
Compose test production cleanup service.

## Этап 7. Lifecycle-aware минимизация raw data

Расширить существующий cleanup и места создания parser payload без отдельного
retention subsystem или новой таблицы.

### Правила хранения

1. Пока документ находится в parsing, mapping или review, сохранять original,
   `raw_text_by_page_json` и `raw_tables_json`, если они нужны доступным
   server capabilities.
2. Для `IMPORTED` и `IGNORED` документов после существующего
   `upload_retention_hours`:
   - очистить полный page text и raw tables;
   - оставить `control_totals_json`, validation result, parser identity и
     нормализованные `RawTransaction`/`Operation`;
   - не менять подтверждённые проводки, balances, reports и dedupe hashes.
3. Для `FAILED_TO_PARSE` после того же retention window очистить extracted raw,
   оставив статус и sanitized error. До cutoff source/raw сохраняются для
   диагностики или retry.
4. Для `REQUIRES_REVIEW` не очищать данные, пока mapping/review остаётся
   доступным. Source продолжает жить по действующей retention policy; raw
   tables обеспечивают не-coordinate mapping после удаления original.
5. Не очищать `RawTransaction` целиком. При создании формировать
   parser-specific `raw_payload` по whitelist: provenance, стабильный
   `source_row_id` и metadata правил без полных исходных строк, headers и
   дублирующих detail lines.
6. Raw-поля даты, суммы и описания сохранять там, где они нужны review и
   normalization diagnostics. Удалять их можно только после отдельного
   consumer audit и characterization tests.

После очистки API возвращает `raw_tables=null`; существующий mapping capability
должен сообщать `RAW_TABLES_UNAVAILABLE`, а не падать. Undo подтверждённой
операции должен продолжать работать по `RawTransaction` и `Operation`, но
повторный mapping после истечения retention window сознательно недоступен без
повторной загрузки файла.

### Acceptance criteria

- mapping preview/import и coordinate mapping работают до cleanup boundary;
- review, classification, rules, confirmation и undo не используют удаляемый
  full page/table payload;
- после cutoff у `IMPORTED`, `IGNORED` и `FAILED_TO_PARSE` отсутствуют полный
  page text и raw tables;
- `REQUIRES_REVIEW` сохраняет данные, необходимые разрешённым действиям;
- balances, reports, confirmed operations и dedupe не меняются;
- detail/mapping API корректно сообщает отсутствие raw tables;
- cleanup идемпотентен, workspace-scoped и не логирует удалённые данные;
- новые backups не содержат уже очищенный raw payload; старые копии удаляются
  только по отдельной действующей backup-retention policy.

### Тесты

- characterization tests mapping preview/import, review, rules, confirmation,
  undo и dedupe до реализации очистки;
- cleanup до/на/после retention boundary для каждого document status;
- сохранение `REQUIRES_REVIEW` raw data;
- отсутствие full source lines в parser `raw_payload` при сохранении нужного
  provenance и rule metadata;
- API behavior после `raw_tables=null`;
- PostgreSQL integration test, доказывающий, что очистка raw не изменяет
  `Operation` и ledger balances.

## Этап 8. Rollout

1. Выпустить terminal failure transaction, active-account check и PDF limits.
2. Выпустить sidecar isolation.
3. Выпустить Telegram streaming.
4. Выполнить sanitized PDF/XLSX и synthetic timeout/OOM smoke на целевом VPS.
5. Включить Nginx limits.
6. Запустить cleanup service.
7. Включить raw-data cleanup после прохождения characterization и ledger tests.
8. Наблюдать 429, timeout/OOM classification, cleanup restarts, app memory и
   disk usage.
9. Только после успешного smoke приглашать недоверенных uploaders.

Production smoke должен подтвердить:

- environment sidecar не содержит секретов;
- sidecar не имеет маршрута к PostgreSQL, API и интернету;
- parser timeout/OOM не нарушает app `/health` и обычные API reads;
- failed attempt терминальный, source сохранён;
- истёкший terminal document не содержит full page text/raw tables, но его
  операции, balances, reports и undo работают;
- logs не содержат raw financial data и storage paths.

## Обязательные проверки

```bash
UV_CACHE_DIR=/tmp/booker-tee-uv-cache uv run ruff format .
UV_CACHE_DIR=/tmp/booker-tee-uv-cache uv run ruff check .
UV_CACHE_DIR=/tmp/booker-tee-uv-cache uv run ty check
UV_CACHE_DIR=/tmp/booker-tee-uv-cache uv run pytest \
  tests/features/imports \
  tests/features/chat_integrations/test_service_upload.py \
  tests/features/chat_integrations/test_providers.py \
  tests/api/test_import_upload_api.py \
  tests/core/test_nginx_upload_limits.py \
  tests/core/test_production_parser_service.py \
  tests/core/test_production_cleanup_service.py -q
UV_CACHE_DIR=/tmp/booker-tee-uv-cache uv run pytest -q
cd frontend && npm run check
./scripts/production-preflight.sh
./scripts/release-gate.sh
docker compose -f compose.production.yaml config -q
```

Ранее зависавший low-level `UploadFile` storage test запускается отдельно с
diagnostic timeout. Suite нельзя считать прошедшим, если зависание сохраняется.

## Сознательно исключено

- AV/CDR и внешняя передача финансовых файлов;
- OCR/AI;
- Celery, Redis, persistent queue и второй backend;
- parser DB access или uploads mount;
- новая DB migration;
- внешний object storage;
- полная distributed rate limiting без подтверждённой необходимости;
- произвольное доверие `X-Forwarded-For`;
- retry/reparse UX вне отдельного продуктового запроса.

## Executor handoff

Перед началом реализации зафиксировать baseline и текущий `git status`.
Существующие пользовательские изменения в `.env.example`, `compose.yaml` и
`src/app/core/settings.py` не откатывать; согласовать реализацию с ними.
Выполнять этапы последовательно, с отдельной проверкой после каждого этапа.
