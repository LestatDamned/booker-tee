# План первого production-деплоя

Статус: active.

Цель — безопасно опубликовать Booker Tee для ограниченного круга пользователей,
с регистрацией только по приглашениям и рабочей Telegram-интеграцией.

План рассчитан на один VPS:

```text
Internet
  -> Nginx (80/443, TLS, rate limits)
  -> FastAPI + React build (127.0.0.1:8000)
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

## 2. Включить регистрацию только по приглашениям

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

## 3. Подготовить Telegram webhook

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

## 4. Создать production image и Compose

Текущий `compose.yaml` предназначен для разработки: он публикует PostgreSQL и
FastAPI, монтирует исходники и запускает Uvicorn с `--reload`. Для production
нужен отдельный `compose.production.yaml`.

Требования:

1. Использовать собранный immutable application image.
2. Не монтировать исходники и не запускать `uv sync` при старте.
3. Не использовать `--reload`.
4. Не публиковать PostgreSQL на host network.
5. FastAPI привязать только к `127.0.0.1:8000`.
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

## 5. Настроить Nginx и TLS

Nginx работает как единственная публичная точка входа.

Требования:

1. Открыть `80/443`; HTTP перенаправлять на HTTPS.
2. Получить и автоматически обновлять сертификат Let's Encrypt.
3. Проксировать запросы на `127.0.0.1:8000`.
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
