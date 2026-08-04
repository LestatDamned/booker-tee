# Stage 07 / Wave C: Users And Authentication

Статус: active. Slice 1 и increments 2.0–2.3 завершены 2026-08-04; следующий
increment — 2.4 Email identity change and account deactivation.

Этот child stage переносит оставшийся authenticated профиль и public auth flow
из Jinja в React и доводит текущую email/password-аутентификацию до полного
пользовательского цикла:

```text
регистрация -> подтверждение email -> personal workspace -> session
вход -> работа -> управление профилем и сессиями -> выход
забытый пароль -> восстановление -> отзыв старых сессий
смена email/пароля -> повторная проверка -> безопасное продолжение работы
деактивация -> отзыв сессий без удаления финансовой истории
```

План сохраняет существующие PostgreSQL `UserSession`, opaque cookie,
workspace membership и application-owned transaction boundaries. Он не вводит
внешний identity provider, JWT, новый frontend framework, Redis, очередь или
универсальную auth-инфраструктуру.

## Решение

Реализация состоит из двух обязательных vertical slices:

| Порядок | Slice                        | Пользовательский результат                                                                                    |
| ------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 1       | React parity и versioned API | Входит, регистрируется, открывает и редактирует профиль, выходит через React                                  |
| 2       | Полный lifecycle и cleanup   | Подтверждает email, восстанавливает и меняет credentials, управляет сессиями и безопасно деактивирует аккаунт |

Passkeys, TOTP, security-event history и физическое удаление пользователя не
входят в этот stage. Они требуют отдельного доказанного product/security need.

## Заметка к планированию Slice 2

Slice 2 не выполняется одним большим изменением. Он разделён на шесть
последовательных vertical increments: безопасная schema/contract foundation,
verification-first signup, password recovery, управление сессиями, изменение
identity/деактивация и только затем SSR cleanup. Каждый increment должен
оставлять production-сборку работоспособной и имеет собственный gate.

Принятые planning defaults:

- текущий password-only flow рассматривается как AAL1; absolute session timeout
  остаётся `14 days`, добавляется idle timeout `1 hour`, а `last_seen_at`
  записывается не чаще одного раза в `5 minutes`;
- verification token действует `24 hours`, reset и change-email token —
  `30 minutes`; все token values имеют не менее 32 random bytes, хешируются и
  являются single-use;
- reset password не создаёт новую session: после успеха пользователь входит
  обычным login, а все старые sessions уже отозваны;
- password/email change и account deactivation требуют current password в том
  же request; после изменения credential текущая session ротируется, остальные
  отзываются;
- self-deactivation разрешена только после устранения shared-workspace owner
  blockers. Sole-member workspaces деактивируются тем же transaction-owned
  application workflow; финансовые записи сохраняются;
- интерфейс использует формулировку «Деактивировать аккаунт», а не «Удалить»:
  hard delete, anonymization и обещание retention period в этот stage не входят;
- production delivery начинается с одного SMTP adapter на Python stdlib и
  test-capturing implementation. API-провайдер, очередь, outbox и email SDK не
  добавляются без подтверждённой потребности;
- public auth throttling хранится в одной bounded PostgreSQL bucket table. IP
  из произвольного `X-Forwarded-For` не считается доверенным; deployment edge
  может дополнительно ограничивать трафик.

До production rollout остаются deployment inputs, а не архитектурные решения:
SMTP host/credentials, verified sender/domain и canonical HTTPS
`PUBLIC_BASE_URL`. Production startup должен отклонять включённую регистрацию
или recovery, если эти значения отсутствуют.

## Исходное состояние перед Slice 2

Этот baseline зафиксирован при планировании. Актуальный результат
каждого завершённого increment описан в его `Completion record` ниже.

### Backend

- `User` хранит `email`, `password_hash`, optional `name` и `is_active`.
- Пароли хешируются Argon2id через установленный `pwdlib`.
- `UserSession` хранит hash случайного opaque token, current workspace,
  `last_seen_at`, absolute expiry и revoke timestamp.
- Registration одним commit создаёт user, personal workspace, owner membership,
  workspace audit event и session.
- Login выбирает первый active membership или создаёт personal workspace, если
  membership отсутствует.
- Session cookie имеет `HttpOnly`, configurable `Secure`, `SameSite=Lax` и
  общий path `/`.
- Authenticated SSR и JSON mutations используют session-bound CSRF.
- `safe_next_path()` принимает только site-relative path и по умолчанию ведёт
  в `/app/workspaces`.

### Presentation

- `GET/POST /login`, `GET/POST /signup`, `GET /users` и `POST /logout`
  принадлежат одному legacy users router.
- React читает только `GET /api/v1/session`.
- `AppShell` ведёт user card на SSR `/users`.
- React Router временно использует `basename=/app`.
- Public workspace invitation preview остаётся минимальным SSR bridge и
  использует login/signup continuation.

### Исходные gaps

- email не подтверждается;
- recovery и смены пароля/email нет;
- нет управления активными сессиями;
- password validation проверяет только длину `8`;
- login/signup/recovery rate limiting отсутствует;
- session resolution обновляет `last_seen_at` и делает commit почти на каждом
  authenticated request;
- профиль read-only;
- `is_active` не выражает момент деактивации;
- конкурентный signup полагается на database unique constraint, но ожидаемый
  conflict не переведён в стабильную application/API ошибку.

Перед реализацией inventory сверяется с актуальным кодом и тестами. Этот раздел
не является причиной сохранять историческое поведение, если оно небезопасно.

## Scope

### Входит

- React login, signup и authenticated profile;
- JSON auth/account API под `/api/v1`;
- email verification и resend;
- forgot/reset password;
- изменение имени, email и пароля;
- current-session logout;
- список user sessions, revoke одной и revoke остальных;
- rate limiting public credential endpoints;
- server-side idle и absolute session expiry;
- деактивация аккаунта с workspace ownership blockers;
- безопасное продолжение invitation flow;
- replacement redirects и удаление legacy users presentation.

### Не входит

- passkeys/WebAuthn, TOTP, SMS и social login;
- hosted auth, Keycloak, ZITADEL или другой identity service;
- новый RBAC или перенос `WorkspaceMember` в users;
- admin user directory;
- device fingerprinting, geolocation и IP history;
- hard delete, каскадное удаление или автоматическая анонимизация финансовой
  истории;
- email queue/outbox до появления реального delivery/retry требования;
- общий routing cutover с удалением `/app` prefix.

## Ownership boundary

```text
users
  identity, credentials, verification, sessions, account lifecycle

workspaces
  membership, role, invitation, ownership, financial access
```

Account endpoints не зависят от active current workspace. Пользователь должен
иметь возможность сменить пароль, отозвать сессии или выйти, даже если current
workspace деактивирован или membership изменён.

Для account API используется узкая authenticated-session dependency, которая
возвращает current `User` и `UserSession` без создания `WorkspaceContext`.
Workspace-dependent API продолжает использовать существующий request context.

## Data changes

Минимальная backward-compatible migration:

```text
users
  + email_verified_at nullable timestamptz
  + deactivated_at nullable timestamptz

user_sessions
  + user_agent_summary nullable varchar

user_tokens
  id
  user_id
  purpose: verify_email | reset_password | change_email
  token_hash
  target_email nullable
  created_at
  expires_at
  consumed_at nullable

auth_rate_limits
  bucket_hash primary key
  attempt_count
  window_started_at
  expires_at
```

Правила migration:

- существующие active users получают `email_verified_at = created_at`, чтобы
  migration не заблокировала действующие аккаунты;
- plaintext token не сохраняется;
- `(purpose, token_hash)` уникален;
- active token lookup индексирован по hash и expiry;
- consumed/expired token не может быть использован повторно;
- current `password_hash` остаётся обязательным: passwordless user пока нет;
- `is_active=false` и `deactivated_at` блокируют создание новой сессии;
- hard delete и `ON DELETE CASCADE` для финансовой истории не добавляются.
- rate-limit bucket key строится как HMAC от scope и account/network key;
  plaintext email и IP в bucket table не сохраняются;
- expired rate-limit rows удаляются opportunistically; отдельный scheduler для
  этого не вводится.

Одна таблица `user_tokens` обслуживает три одноразовых identity-действия. Новая
таблица или generic token framework не создаются без нового независимого
контракта.

## Registration contract

Первая версия использует одну обычную форму:

```text
email + optional name + password
  -> normalize and validate
  -> create unverified User
  -> save hashed verification token
  -> send verification link
  -> show generic accepted state
```

До verification не создаются personal workspace, membership и session.

Verification:

```text
valid single-use token
  -> mark email verified
  -> create personal workspace + owner membership + audit event
  -> create session
  -> commit once
  -> set cookie
  -> continue to validated next path
```

Если signup пришёл из invitation preview, validated continuation сохраняет
путь приглашения. Внешний URL, protocol-relative URL и произвольный host не
принимаются.

Повторный signup с существующим email не меняет password или profile и не
раскрывает состояние аккаунта. Database unique violation переводится в тот же
публичный результат, а не в `500`.

## Password policy

- configurable минимум для нового password-only credential: стартовое значение
  `8`, меняется через `BOOKER_TEE_PASSWORD_MIN_LENGTH` без изменения кода;
- существующие hash продолжают приниматься при корректном login;
- разрешены длинные passphrases, Unicode, whitespace, paste и password
  managers;
- uppercase/digit/symbol composition rules не вводятся;
- новый пароль сравнивается с локальным blocklist распространённых или
  скомпрометированных значений;
- календарная принудительная смена пароля не вводится;
- успешный login обновляет устаревшие Argon2id parameters, если `pwdlib`
  сообщает о необходимости rehash.

## Session policy

- cookie остаётся opaque, `HttpOnly`, `Secure` в production и `SameSite=Lax`;
- session expiry проверяется server-side;
- absolute timeout остаётся configurable;
- добавляется configurable idle timeout;
- `last_seen_at` обновляется не чаще принятого небольшого интервала, а не на
  каждый request;
- logout отзывает server record до удаления cookie;
- password reset и account deactivation отзывают все active sessions;
- password/email change отзывают остальные sessions и обновляют текущую
  session только по явному contract;
- session list не публикует token hash, current workspace details, IP или
  private headers;
- user-agent преобразуется в bounded безопасную подпись устройства; полный
  header не логируется и не возвращается.

## API boundary

### Public auth

```text
GET    /api/v1/auth/config
POST   /api/v1/auth/signup
POST   /api/v1/auth/email-verifications
POST   /api/v1/auth/email-verification-requests
POST   /api/v1/auth/login
POST   /api/v1/auth/password-reset-requests
POST   /api/v1/auth/password-resets
```

### Authenticated account

```text
DELETE /api/v1/auth/session

GET    /api/v1/account
PATCH  /api/v1/account
PATCH  /api/v1/account/password
POST   /api/v1/account/email-change-requests
POST   /api/v1/account/email-changes
GET    /api/v1/account/sessions
DELETE /api/v1/account/sessions/{sessionId}
DELETE /api/v1/account/sessions/others
POST   /api/v1/account/deactivation
```

API возвращает DTO и stable error codes, не ORM objects, HTML, русские action
URLs или template state. Login/verification устанавливают cookie через FastAPI
response adapter; React не получает session token.

### Public mutation protection

- только JSON request body;
- same-origin `Origin`/Fetch Metadata validation;
- permissive CORS не включается;
- account- и network-scoped throttling;
- generic response для signup, verification resend и password reset request;
- `429` имеет стабильный code и не раскрывает наличие user;
- CAPTCHA не добавляется без доказанного abuse и отдельного accessibility
  решения;
- новый Redis или иной service только ради rate limiting не вводится: сначала
  используется существующий deployment edge, а при его отсутствии — bounded
  PostgreSQL policy.

Authenticated mutations используют существующий `X-CSRF-Token` contract.

## React routes and state

На время Stage 07:

```text
/app/auth/login
/app/auth/signup
/app/auth/verify-email
/app/auth/forgot-password
/app/auth/reset-password
/app/profile
/app/profile/security
/app/profile/sessions
```

Исторические `/login`, `/signup` и `/users` становятся query-preserving
redirects только после replacement gate. Удаление `/app` prefix остаётся общим
решением Stage 07.

Auth pages используют отдельную feature-local композицию без authenticated
`AppShell`. Profile/security/sessions используют `AppShell` и существующие
`PageFrame`, `PageHeader`, form/error/notice/confirmation primitives.

State ownership:

- URL: safe continuation и reset/verification token только на входе в route;
- loader/server: account/session snapshots;
- feature-local: form draft, password visibility, pending/error и
  confirmation state;
- server only: user status, token validity, throttling, session validity,
  workspace ownership blockers.

Token удаляется из видимого URL через replace navigation после первого
успешного чтения/submit, чтобы он не оставался в history дольше необходимого.

## UX contract

- один primary action на экран;
- видимые labels, подходящий `autocomplete` и native input semantics;
- password show/hide без блокировки paste;
- validation после blur/submit, а не шум на каждый символ;
- field error рядом с control и общий error summary;
- после failed submit focus переходит на первое invalid field;
- pending блокирует повторный submit и остаётся видимым в кнопке;
- введённый email/name не теряется после ожидаемой ошибки;
- generic security copy остаётся полезной: сообщает следующий шаг, не наличие
  аккаунта;
- resend имеет cooldown и понятный status;
- destructive account action отделён от обычных settings и подтверждается;
- control height, focus, contrast, live regions и reduced motion соответствуют
  существующему React foundation;
- browser checks выполняются минимум на `1440x1000`, `920x900`, `390x844` и
  reflow `320px` в Mocha и Latte.

## Slice 1: React Parity And API

### Server

1. Добавить auth/account schemas и routers под `/api/v1`.
2. Переиспользовать существующие registration/login/logout workflows без
   преждевременной смены session model.
3. Добавить authenticated-session dependency без workspace requirement.
4. Перевести expected `UserError` в stable API envelope и field errors.
5. Сохранить cookie и safe continuation contract.

### Frontend

1. Добавить focused auth/account API clients поверх общего transport.
2. Собрать login/signup через существующие form primitives.
3. Добавить editable profile с именем и read-only email.
4. Добавить API logout в profile и shell.
5. Не поднимать auth form abstraction в shared UI до реального повторяющегося
   контракта.

### Gate

- React повторяет действующие успешные login/signup/logout/profile paths;
- invalid credentials, closed signup, invalid next и expired session покрыты;
- cookie не доступна JavaScript;
- invitation continuation сохраняется;
- SSR остаётся рабочим до завершения Slice 2 и общего replacement gate.

Slice 1 completed 2026-08-04: versioned auth/account API, React
login/signup/profile, shell/profile logout, safe continuation, stable errors,
workspace-independent account context and generated OpenAPI types are in place.
Backend contract tests, the full frontend suite and production build pass.

Browser gate completed in Chromium with both Mocha and Latte themes at
`1440x1000`, `920x900`, `390x844` and `320x844` (24 visual combinations). The
functional run covered login validation and error announcement, signup with an
authenticated session, invitation continuation, rejection of an external
continuation, profile update with read-only email, profile and shell logout,
expired-session recovery and the JavaScript-inaccessible session cookie. No
horizontal overflow was found, including the `320px` reflow check. Legacy SSR
remains operational until the Slice 2 replacement gate.

## Slice 2: Full Lifecycle And Cleanup

### 2.0 Foundations: schema, policy and delivery boundary

Server:

1. Добавить backward-compatible Alembic migration для `email_verified_at`,
   `deactivated_at`, `user_agent_summary`, `user_tokens` и
   `auth_rate_limits`.
2. Backfill существующих active users как verified через `created_at`; новые
   nullable columns добавлять до backfill/constraints, чтобы rolling migration
   не блокировала старый код.
3. Добавить token issue/consume repository queries с row lock и одним
   application-owned commit. При выпуске нового token того же purpose старые
   active tokens пользователя инвалидируются.
4. Реализовать два независимых throttle buckets: account key и network key.
   Не использовать один combined `IP+email` bucket и не блокировать аккаунт
   навсегда; ожидаемый результат — временный generic `429`.
5. Добавить same-origin policy для public JSON mutations: reject
   `Sec-Fetch-Site: cross-site`, затем проверять exact `Origin` against trusted
   public origin. Authenticated mutations сохраняют существующий CSRF header.
6. Ввести узкий identity-email message type и delivery callable. SMTP находится
   в infrastructure, а token/workspace policy — в application code. Test
   delivery только захватывает message; token и полный URL не логируются.
7. Отправлять email после commit через native response background task. Без
   durable queue delivery может потеряться при аварийном shutdown; resend —
   явный recovery path и граница этой минимальной реализации.
8. Расширять текущий `service.py` только до cohesion threshold. Когда истории
   реально разделятся, использовать `authentication.py`, `account.py` и
   `tokens.py`; не добавлять Protocol для единственного repository и не строить
   generic identity framework.

Gate 2.0:

- upgrade/downgrade и backfill доказаны migration tests;
- raw token, full email и full user-agent не появляются в БД/logs/API;
- concurrent consume даёт один результат, а throttling атомарен;
- production settings fail fast без canonical HTTPS URL и SMTP configuration;
- старые verified users продолжают login без изменения workspace/session.

Completion record 2026-08-04:

- migration `20260804_0022` добавляет identity timestamps, bounded session
  summary, hashed single-use tokens и HMAC-keyed throttle buckets;
- existing active users backfilled как verified; upgrade, downgrade и repeat
  upgrade проверены на отдельной PostgreSQL database;
- token replacement/consume использует row locks, throttle increment — atomic
  PostgreSQL upsert; concurrency test доказал одного token winner и отсутствие
  lost updates;
- login/signup JSON API отклоняет missing/cross-site Origin и принимает
  same-origin Fetch Metadata;
- identity email boundary использует Python stdlib SMTP, STARTTLS и
  `asyncio.to_thread`; secrets отсутствуют в `repr`, token hashes и rate-limit
  keys не раскрывают исходные значения;
- production fail-fast включается вместе с
  `BOOKER_TEE_IDENTITY_EMAIL_ENABLED`; flag остаётся выключенным до cutover 2.1,
  поэтому действующий signup не обещает email, который пока не отправляется;
- OpenAPI/generated TypeScript contracts обновлены; relevant backend,
  PostgreSQL и frontend tests, а также production build прошли.

### 2.1 Verification-first signup

Server:

1. Изменить signup: создать unverified user и verification token, но не
   workspace, membership или session; вернуть generic accepted response.
2. Для existing email вернуть тот же response и не менять password/profile.
   Database unique race переводится в тот же публичный результат.
3. Resend выдаёт новый token только подходящему unverified user, но response и
   timing path не раскрывают наличие или состояние аккаунта.
4. Email link открывает React route. `GET` не меняет state: verification
   выполняется только явным `POST`, чтобы mail scanners/prefetch не потребляли
   token.
5. Verification под row lock атомарно consume token, отмечает email verified,
   создаёт ровно один personal workspace, owner membership, audit event и новую
   session.
6. `next` не хранится как authority в token: React передаёт только
   site-relative value, а server повторно применяет `safe_next_path()`.

Frontend:

1. Signup показывает generic «Проверьте почту» state с resend cooldown и
   ссылками «Войти»/«Восстановить пароль».
2. `/app/auth/verify-email` захватывает token из URL и сразу очищает visible URL
   через replace navigation. До явного подтверждения mutation не выполняется.
3. Invalid/expired/consumed token получает единый recovery screen с resend, без
   технических подробностей.
4. Сохранить invitation continuation и существующие form primitives; отдельный
   auth-form framework не создавать.

Gate 2.1:

- unverified user не может login и не имеет workspace/session;
- verification и concurrent verification не создают duplicate workspace;
- known/unknown signup и resend имеют одинаковый публичный contract;
- browser flow `signup -> captured email -> verify -> workspace` проходит вместе
  с invitation continuation.

Completion record 2026-08-04:

- signup теперь создаёт только unverified user и hashed 24-hour token; workspace,
  membership и session появляются одной transaction только после verification;
- existing email и database unique race дают тот же generic `202`, не меняют
  password/name и не раскрывают состояние аккаунта;
- resend использует generic response, заменяет active token только для
  подходящего unverified user и ограничен account/network PostgreSQL buckets с
  `Retry-After` и стабильным `auth_rate_limited`;
- email отправляется после commit через FastAPI background task и узкий
  delivery callable; production signup требует включённый identity email,
  canonical HTTPS URL, sender и SMTP configuration;
- `POST /email-verifications` consume token под row lock, отмечает email
  verified, создаёт один personal workspace, owner membership, audit event и
  opaque session cookie; concurrent signup/verification проверены на
  PostgreSQL;
- React signup показывает generic accepted state и resend cooldown;
  `/app/auth/verify-email` удаляет token из visible URL до явного POST, а
  invalid/expired/consumed state ведёт к generic resend recovery;
- invitation continuation кодируется в email link только после
  `safe_next_path()` и повторно проверяется server-side при verification;
- исторический `GET/POST /signup` больше не обходит verification и переводит в
  canonical React signup с сохранением `next`; legacy login остаётся до общего
  cleanup gate;
- API/OpenAPI, application, React и PostgreSQL tests прошли; Playwright audit
  проверил signup, ready verification и recovery verification на
  `1440x1000`, `920x900`, `390x844` в Mocha и Latte (`18/18` страниц).

Deployment note: локальный/test no-op sender остаётся только при явно
выключенном `BOOKER_TEE_IDENTITY_EMAIL_ENABLED`; для реального пользовательского
journey флаг, HTTPS base URL и SMTP должны быть настроены. Это rollout input, а
не скрытый fallback или логирование raw token.

### 2.2 Password policy, recovery and change

Server:

1. Применять configurable password policy `8..1024` Unicode code points;
   минимум брать из auth config, без composition rules, trim, запрета
   whitespace/paste или календарной смены.
2. Сравнивать весь новый password с локальным pinned blocklist распространённых
   значений и контекстных вариантов Booker Tee. Не вызывать внешний breach API
   из credential flow.
3. На login выполнять эквивалентную password-hash работу и для unknown email,
   чтобы не оставлять простой timing oracle; successful login обновляет hash,
   если установленный `pwdlib` поддерживает `verify_and_update`.
4. Password-reset request всегда возвращает generic accepted response.
   Reset-token single-use, `30 minutes`, не меняет user до успешного submit.
5. Успешный reset меняет hash, инвалидирует все reset tokens и active sessions,
   очищает cookie и ведёт на обычный login с announced success.
6. Authenticated password change требует current password, применяет ту же
   policy, отзывает остальные sessions и ротирует current session/token.
7. Throttling применяется к login, signup, resend, reset request и token
   attempts независимо по account и network buckets. CAPTCHA и hard account
   lock не добавляются.

Frontend:

1. Добавить `/app/auth/forgot-password`, `/app/auth/reset-password` и password
   section в `/app/profile/security`.
2. Использовать visible labels, show/hide, `autocomplete="current-password"` и
   `autocomplete="new-password"`, разрешать paste/autofill.
3. Показывать requirements до submit, field error после blur/submit, error
   summary с focus на первое invalid field и pending state без duplicate submit.

Gate 2.2:

- reset token hashed, expiring, single-use и не работает после password reset;
- все старые cookies отвергаются после reset, текущая session корректно
  ротируется после authenticated change;
- generic responses и `429` не раскрывают существование user;
- forgot/reset/change flows проходят keyboard-only и browser matrix.

Completion record 2026-08-04:

- общий configurable policy применён к signup, reset и authenticated change:
  `8..1024` Unicode code points, локальный pinned blocklist common/context
  passwords, без composition rules, trim, запрета paste или календарной смены;
- login выполняет Argon2id dummy verification для неизвестного email,
  автоматически обновляет устаревший hash через `verify_and_update` и считает
  failed account/network attempts в существующих PostgreSQL buckets;
- generic `POST /password-reset-requests` создаёт hashed single-use token на 30
  минут только для active verified user; `POST /password-resets` не меняет user
  до валидного token/password и после успеха отзывает все reset tokens и
  sessions;
- `PATCH /account/password` требует current password, отзывает остальные
  sessions, ротирует current opaque token и заново устанавливает cookie;
- React добавил `/app/auth/forgot-password`, `/app/auth/reset-password` и
  `/app/profile/security`; формы используют visible labels, native autocomplete,
  show/hide, paste/password-manager semantics, inline errors, error summary,
  focus first invalid field и pending protection;
- новая миграция не потребовалась: `user_tokens`, token purpose и rate-limit
  buckets уже добавлены безопасным foundation 2.0;
- Ruff, ty, OpenAPI contract, full backend (`816 passed, 19 skipped`), full
  frontend (`85 files, 493 passed`), production build и PostgreSQL identity
  suite (`4 passed`) прошли; Mocha/Latte browser audit проверил recovery и
  security pages на `1440x1000`, `920x900`, `390x844` (`18/18` страниц).

### 2.3 Session hardening and management

Server:

1. Проверять absolute и idle expiry server-side при каждом resolution; expired
   record revoke/ignore до выдачи authenticated context.
2. Обновлять `last_seen_at` не чаще `5 minutes`, без commit на каждый request.
3. Сохранять при создании bounded allowlist-based summary вида
   `Chrome · Linux`; неизвестный client становится `Неизвестный браузер`, без
   полного User-Agent, fingerprinting, IP или geolocation.
4. Добавить list-own, revoke-own и revoke-others operations. Repository queries
   всегда фильтруют `user_id`; session token/hash и workspace details не входят
   в DTO.
5. Current session помечается сравнением server-side. Для неё UI использует
   существующий logout; revoke endpoint обслуживает другие sessions.

Frontend:

1. `/app/profile/sessions` показывает current session первой, затем остальные
   по `last_seen_at`, с created/last active и понятным empty state.
2. Revoke одной session и «Завершить остальные» имеют confirmation, pending,
   success announcement и повторную загрузку server snapshot.
3. Не показывать приблизительную геолокацию и не обещать точное определение
   устройства.

Gate 2.3:

- один user не может читать/отзывать чужую session;
- idle/absolute expiry и bounded touch проверены с controllable clock;
- list DTO не содержит secrets/private headers;
- current logout и revoke others доказаны API, React и browser tests.

Completion record 2026-08-04:

- session resolution теперь server-side отзывает absolute-expired и idle
  sessions; idle timeout по умолчанию `1 hour`, absolute lifetime — `14 days`;
- `last_seen_at` обновляется не чаще одного раза в `5 minutes`,
  поэтому обычный authenticated request больше не делает commit;
- при создании session сохраняется только bounded allowlist summary
  вида `Chrome · Linux`; full User-Agent, IP, geolocation и fingerprint не
  сохраняются;
- `GET /api/v1/account/sessions`, `DELETE /sessions/{session_id}` и
  `DELETE /sessions/others` работают только в границах authenticated
  `user_id`; DTO не содержит token/hash, workspace, headers и network data;
- React route `/app/profile/sessions` показывает current session первой,
  даёт завершить одну/остальные через confirmation dialog, а для
  current session использует обычный logout;
- новая migration не потребовалась: `last_seen_at`, absolute `expires_at` и
  `user_agent_summary` уже существовали после foundation 2.0;
- Ruff, ty, OpenAPI contract, full backend (`821 passed, 20 skipped`), full
  frontend (`86 files, 498 passed`), production build и PostgreSQL identity
  suite (`5 passed`) прошли; Mocha/Latte browser audit проверил
  `/app/profile/sessions` на `1440x1000`, `920x900`, `390x844` (`6/6`
  страниц).

### 2.4 Email identity change and account deactivation

Email change:

1. Request требует current password и свободный normalized target email.
2. Старый адрес немедленно получает security notification, новый — single-use
   confirmation link. До подтверждения canonical `users.email` не меняется.
3. Confirm требует authenticated session, повторно проверяет uniqueness под
   lock, меняет email/verified timestamp, отзывает остальные sessions и
   ротирует текущую.
4. После успеха уведомить старый адрес. Failure copy даёт безопасный recovery
   path без раскрытия чужого target email.

Deactivation:

1. Impact endpoint/server result перечисляет blockers и recovery links, но не
   отдаёт финансовые детали вне workspace authorization.
2. Shared workspace с другими active members блокирует действие до передачи
   ownership или явной деактивации workspace. Sole-member owned workspaces
   закрываются через существующую workspace lifecycle policy в той же
   transaction boundary.
3. Confirmation отделена от обычных settings, требует current password и явно
   сообщает: login прекратится, sessions/integrations будут отозваны, финансовая
   история не удалится.
4. Success устанавливает `is_active=false`, `deactivated_at`, отзывает все
   sessions и очищает cookie. Самостоятельной reactivation в этом stage нет.

Gate 2.4:

- email collision/race и stale token не меняют identity;
- old/new email notifications не содержат credential/token leakage;
- account deactivation не оставляет active shared workspace без владельца;
- ни одна финансовая запись не удаляется, все sessions становятся invalid;
- blockers ведут в существующие React workspace ownership actions.

### 2.5 Replacement gate and cleanup

1. Пройти полный test manifest и browser journeys этого документа в Mocha и
   Latte на `1440x1000`, `920x900`, `390x844`, `320x844`, keyboard-only и
   reduced-motion.
2. Сделать `GET /users` redirect на `/app/profile`; `/login` и `/signup`
   сохраняют validated `next` при redirect на React.
3. Удалить legacy POST routes только после browser evidence.
4. Удалить `src/app/templates/users/index.html`, `login.html`, `signup.html`,
   users-only legacy selectors и replacement-only SSR tests после consumer
   search.
5. Public home и workspace invitation SSR сохранить как именованные consumers,
   пока их отдельный cutover не принят.
6. Domain/application/session tests сохранить и расширить; browser tests их не
   заменяют.

Gate 2.5: child stage получает `completed` только после выполнения общего Exit
gate ниже. Если production SMTP/sender ещё не настроен, code complete не равно
production ready.

## Test manifest

### Application and database

- existing users are verified by migration backfill;
- signup creates one unverified user and no workspace/session;
- verification atomically creates exactly one personal workspace, membership
  and session;
- verification/reset/change tokens are hashed, expiring and single-use;
- concurrent signup/verification do not create duplicate users/workspaces;
- inactive, unverified and deactivated users cannot login;
- password reset revokes all sessions;
- change password/email follows the accepted current/other session policy;
- idle and absolute expiry are enforced server-side;
- `last_seen_at` is not written on every request;
- one user cannot list or revoke another user's session;
- deactivation is blocked for unresolved workspace ownership;
- no financial record is deleted by account lifecycle.

### API

- schemas and stable error envelopes;
- generic signup/resend/reset-request response for known and unknown email;
- invalid Origin/CSRF, malformed body and throttling;
- cookie attributes and session rotation;
- `401` vs expected `403/409/422/429` behavior;
- safe continuation rejects external and protocol-relative URLs;
- account API works without an active workspace;
- session DTO omits token/hash/private headers.

### React

- draft preservation and field-error mapping;
- password visibility, paste and autocomplete attributes;
- focus first invalid field and announced summary/status;
- pending prevents duplicate submit;
- verify/reset token URL cleanup;
- unauthenticated and expired-session recovery;
- profile edit, logout, session revoke and deactivation confirmations;
- keyboard-only flow and responsive reflow.

### Browser replacement

```text
signup -> email fixture -> verify -> workspace -> profile -> logout -> login
forgot password -> email fixture -> reset -> old sessions rejected -> login
profile -> change name/password -> list/revoke session -> logout
invitation -> signup/login -> return to invitation -> accept -> React workspace
```

Browser fixture перехватывает только email delivery boundary и не обходит
token/application validation.

## Security references for Slice 2

- [NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html) — password
  length/blocklist, password-manager support and reauthentication guidance.
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
  — generic auth errors, reauthentication and credential-change controls.
- [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
  — single-use URL tokens, uniform responses and reset-session handling.
- [OWASP Email Validation and Verification Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Email_Validation_and_Verification_Cheat_Sheet.html)
  — ownership verification, email-change notifications and anti-enumeration.
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
  — opaque cookies, server-side idle/absolute expiry and invalidation.
- [OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
  — Fetch Metadata, Origin fallback and custom-header CSRF defense.
- [MDN autocomplete](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/autocomplete)
  — `current-password`, `new-password` and browser/password-manager semantics.

## Exit gate

Child stage завершён только когда:

- полный signup/verification/login/recovery/profile/session/logout lifecycle
  работает через React и `/api/v1`;
- account management не зависит от active workspace;
- workspace membership, invitation и ownership остаются server-owned;
- rate limiting, CSRF/origin, token expiry/single-use и cookie contracts
  доказаны тестами;
- account lifecycle не удаляет финансовые данные и уважает ownership blockers;
- canonical navigation ведёт в React, compatibility GET сохраняют query;
- realistic browser flows проходят на desktop, tablet и mobile в обеих темах;
- legacy users routes/templates/assets и replacement-only tests удалены;
- public home/invitation SSR имеют именованных consumers;
- Passkeys, MFA, hard delete и external IdP не были добавлены без отдельного
  решения.
