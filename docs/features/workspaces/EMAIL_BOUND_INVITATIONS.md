# Email-bound workspace invitations

Статус: реализовано 10 августа 2026; authenticated browser smoke через transient
share URL пройден 11 августа 2026. Реальная SMTP-доставка остаётся production
rollout gate.

## Проблема

Текущее invitation даёт доступ любому авторизованному пользователю,
который получил ссылку. Для приватных финансовых данных это
недостаточная identity boundary.

Цель: invitation связывает workspace, role и один нормализованный
email. Ссылка остаётся секретным credential, но её недостаточно без
входа в аккаунт с тем же verified email.

## Пользовательский flow

### Создание

1. Owner/admin открывает workspace settings.
2. Вводит email и выбирает доступную роль.
3. API возвращает committed invitation и transient `shareUrl`.
4. React показывает результат и кнопку копирования.
5. Если SMTP настроен, тот же URL отправляется на invitee email
   после commit.

Ошибка email delivery не откатывает invitation. Share URL остаётся
рабочим fallback; отдельная durable delivery queue в этот slice не входит.

### Принятие

```text
open link
  -> public preview: workspace name, role, expiry
  -> login/signup with preserved next path
  -> verified authenticated user
  -> token + normalized user.email check
  -> membership create or removed membership recovery
  -> invitation accepted
  -> current session switches workspace
```

Если пользователь вошёл с другим email, UI не показывает целевой
адрес и не позволяет accept. Ответ объясняет, что нужен другой
аккаунт, не раскрывая email.

## Data contract

`WorkspaceInvitation` получает:

```text
invitee_email  String(320) | null, normalized, indexed
```

Поле nullable только для historical accepted/revoked rows. Все новые pending
invitations обязаны иметь `invitee_email`; это гарантирует application
workflow и test, пока history не будет свёрнута.

Миграция:

1. добавляет nullable column и index
   `(workspace_id, invitee_email, status)`;
2. переводит существующие unbound `pending` invitations в `revoked` с
   `revoked_at=now()`;
3. не изменяет accepted/revoked historical rows;
4. не логирует token или email.

Отзыв pending links — безопасная one-time migration: она не удаляет
membership или financial data, а owner/admin может создать адресное
invitation заново.

## Application contract

### Create

`WorkspaceInvitationService.create(...)`:

1. normalizes email через тот же `normalize_email`, что identity flows;
2. locks workspace и active actor membership;
3. проверяет assignable role и member limit;
4. помечает expired pending invitations для этого email как `expired`;
5. отклоняет duplicate unexpired pending invitation;
6. отклоняет email active/disabled member с понятным reason code;
7. создаёт idempotent invitation и audit event;
8. commits до email delivery.

Повтор с тем же `Idempotency-Key`, email и role возвращает тот же
committed invitation и share URL. Тот же key с другим email или role
возвращает `409 idempotency_conflict`.

### Accept

Accept в одной transaction:

1. finds token hash без раскрытия invalid/replayed state;
2. locks workspace, invitation и authenticated session;
3. проверяет active workspace, pending status и expiry;
4. требует active user с verified email;
5. сравнивает normalized `user.email` и `invitee_email`;
6. создаёт или восстанавливает membership;
7. consumes invitation, records audit event и switches только current
   browser session;
8. commits once.

Membership outcomes:

| Existing membership | Outcome                                                            |
| ------------------- | ------------------------------------------------------------------ |
| none                | create active membership with invitation role                      |
| active              | reject as already member                                           |
| disabled            | reject; owner/admin must reactivate explicitly                     |
| removed             | reactivate the same row with invitation role and a new `joined_at` |

Повторное принятие consumed token не меняет membership и возвращает
тот же privacy-safe unavailable response, что invalid/revoked/expired token.

## API contract

### Create

```http
POST /api/v1/workspaces/{workspaceId}/invitations
Idempotency-Key: <uuid>

{
  "email": "anna@example.com",
  "role": "editor"
}
```

Response сохраняет текущую shape и добавляет email в list item:

```json
{
  "invitation": {
    "id": "...",
    "inviteeEmail": "anna@example.com",
    "role": "editor",
    "status": "pending",
    "expiresAt": "..."
  },
  "invitations": {},
  "shareUrl": "https://example.test/app/workspaces/invitation#token=<token>",
  "replayed": false
}
```

`shareUrl` остаётся transient create/replay field и никогда не попадает в
directory response.

### Stable errors

| HTTP/code                       | Meaning                                                   |
| ------------------------------- | --------------------------------------------------------- |
| `409 pending_invitation_exists` | для email уже есть active pending invitation              |
| `409 idempotency_conflict`      | key replayed с другим command fingerprint                 |
| `422 already_member`            | email принадлежит active member                           |
| `422 member_disabled`           | нужно reactivate existing membership                      |
| `422 member_limit_reached`      | достигнут explicit workspace member limit                 |
| `422 invitation_role_forbidden` | actor не может назначить role                             |
| `403 invitation_email_mismatch` | authenticated account не совпадает, email не раскрывается |
| `404 invitation_not_found`      | invalid, expired, revoked или replayed token              |

Public preview по-прежнему отдаёт только workspace name, role и expiry.
Preview и accept используют стабильные `POST /api/v1/workspaces/invitations/preview`
и `POST /api/v1/workspaces/invitations/accept`; token передаётся только полем
`invitationToken` JSON body.
`invitee_email`, member existence и delivery state не публикуются.

## Email delivery

Переиспользуются `IdentityEmail`, `IdentityEmailSender` и текущий SMTP adapter.
Новый builder не знает о workspace repository:

```python
def build_workspace_invitation_message(
    *,
    recipient: str,
    workspace_name: str,
    inviter_name: str,
    role: str,
    invitation_url: str,
    expires_at: datetime,
) -> IdentityEmail: ...
```

Письмо не включает financial data, account names и member list. API route
планирует background send только после успешного application commit.

## React UX

- invitation form требует email и role;
- pending list показывает email, role, creator time и expiry;
- share URL виден только сразу после create/replay;
- conflict о duplicate invitation предлагает отозвать старое, а не
  создаёт ещё одно;
- `member_disabled` ведёт owner/admin к member reactivation;
- accept mismatch показывает «Войдите в аккаунт, для которого
  создано приглашение» без раскрытия адреса;
- form сохраняет focus, field errors и pending state по общим form
  rules.

## Security and privacy

- token хранится только как hash;
- invitation/list/API logs не содержат token и email;
- preview сохраняет `Cache-Control: no-store` и
  `Referrer-Policy: no-referrer`;
- accept требует same-origin CSRF, active session и verified email;
- foreign workspace/invitation IDs дают privacy-safe not-found;
- email comparison использует canonical identity normalization, а не
  отдельную invitation normalization;
- ownership/member/invitation transitions остаются под workspace row
  lock.

## Tests and exit gate

Application/PostgreSQL:

- create persists normalized email and token hash;
- idempotent replay compares email and role fingerprint;
- same email concurrent create has one pending winner;
- accept succeeds only for matching verified email;
- wrong-account accept changes nothing;
- expired/revoked/replayed tokens share unavailable behavior;
- accept versus revoke has exactly one winner;
- two matching sessions accepting have one winner;
- removed membership is recovered without violating unique membership;
- active/disabled membership is not silently replaced;
- foreign workspace and invitation IDs remain masked;
- migration revokes legacy unbound pending invitations.

API/React:

- create request requires valid email and role;
- directory exposes email only to authorized member managers;
- public preview never exposes email;
- share URL is absent from directory payload;
- signup/login preserves invitation destination;
- mismatch, duplicate, disabled-member and limit states have usable UX;
- keyboard/focus behavior and narrow viewport are covered.

Автоматические backend, PostgreSQL concurrency, OpenAPI и frontend gates пройдены.
Локальный authenticated invite → accept smoke через transient share URL также
пройден. Финальный эксплуатационный gate — повторить этот путь с реальной SMTP
конфигурацией перед production rollout.
