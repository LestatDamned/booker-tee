# Workspace collaboration

Статус: действующий security и collaboration contract для малой команды.

Workspace — строгая граница финансовых данных. Collaboration использует те же
application services, repositories и ledger, а не отдельный team backend.

## Роли

| Capability                    | Owner | Admin | Editor | Uploader | Analyst |    Viewer |
| ----------------------------- | ----: | ----: | -----: | -------: | ------: | --------: |
| Финансовые reads              |     ✓ |     ✓ |      ✓ |        ✓ |       ✓ |         ✓ |
| Financial mutations           |     ✓ |     ✓ |      ✓ |        — |       — |         — |
| Import management             |     ✓ |     ✓ |      ✓ |        ✓ |       — |         — |
| Raw import data               |     ✓ |     ✓ |      ✓ |        ✓ |       — | read-only |
| Team directory/activity       |     ✓ |     ✓ |      — |        — |       — |         — |
| Members/invitations           |     ✓ |     ✓ |      — |        — |       — |         — |
| Ownership/workspace lifecycle |     ✓ |     — |      — |        — |       — |         — |

Конкретную capability всегда проверяет backend policy. Session capabilities
нужны React для navigation, но не заменяют server authorization. Uploader
управляет import documents/mapping, но не подтверждает ledger mutation. Analyst
не получает raw imported data; viewer не получает mutation.

## Invitations

Invitation связана с normalized verified email, workspace, role, expiry и
single-use token. Public preview и ошибки не раскрывают наличие user или
membership. Accept требует authenticated user с совпадающим verified email,
активный workspace и pending invitation.

Create, resend, revoke и accept идемпотентны или возвращают стабильный conflict.
Email delivery не владеет membership transaction; failure сохраняет безопасное
состояние для retry. Реальная SMTP-доставка остаётся production gate.

## Membership и lifecycle

Поддерживаются role change, disable/reactivate, self-leave, ownership transfer и
workspace deactivate/restore. Нельзя удалить/отключить последнего owner или
обойти ownership transfer. Опасные переходы используют optimistic version и,
где нужен единственный победитель, row lock.

При потере доступа active workspace в session заменяется валидным fallback без
раскрытия данных прежнего workspace.

## Activity

Owner/admin видит единый keyset-paginated journal значимых administrative и
financial mutations. Event записывается в той же transaction, что и mutation,
с actor, workspace, entity reference, timestamp и versioned typed details.

Details содержат только безопасные identifiers, amounts/currencies и outcome;
tokens, email delivery payloads, raw documents, descriptions и account numbers
не сохраняются. Это operational history, не compliance audit. Event bus/outbox
не нужен без external consumer.

## Concurrency и isolation

- Каждый repository lookup фильтрует `workspace_id` или валидирует owned parent.
- Client workspace id и role никогда не считаются доказательством доступа.
- Version conflicts возвращают stable `409`; replay не повторяет side effects.
- DB constraints защищают unique membership/invitation и ownership invariants.
- PostgreSQL RLS не используется при текущем single-backend access model.
- Явные limits малой команды возвращают ошибку, а не молча обрезают directory.

Обязательные проверки: two-workspace isolation, cross-role API/chat/browser
access, concurrent invitation/membership/ownership transitions, session fallback
и отсутствие sensitive activity details.
