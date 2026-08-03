# ADR-0006: Workspace Migration Policy

Status: accepted 2026-08-03.

## Context

Stage 7 Wave C переносит authenticated Workspaces workflow с legacy
SSR/Jinja/HTMX на React. Workspace является строгой границей финансовых данных,
а его переключение, membership и lifecycle влияют на session, Chat,
integrations и все workspace-owned aggregates.

Аудит и фактический inventory находятся в
[`frontend/plan/workspaces`](../../frontend/plan/workspaces/README.md). Решения
D1–D14 приняты владельцем проекта 2026-08-03 без отклонений.

## Decision

### Scope and routes

- Первый production slice включает directory, create и explicit switch.
  Settings, members и invitations мигрируют отдельными vertical slices.
- Canonical authenticated routes — `/app/workspaces` и
  `/app/workspaces/:workspaceId/settings`.
- После replacement gate исторический `GET /workspaces` становится
  query-preserving redirect; legacy POST routes не перенаправляются.
- Directory отвечает за выбор и создание, settings — за identity, access,
  invitations и activity.
- Public invitation accept первоначально остаётся отдельным hardened SSR bridge.

### Product and authority policy

- Personal и shared workspaces используют общую UI geometry с type- и
  capability-aware содержимым.
- Сохраняются роли `owner`, `admin`, `editor`, `uploader`, `analyst`, `viewer`.
  Сервер возвращает capabilities и reason codes; React не выводит authority из
  названия роли.
- Authoritative owner ровно один и согласован с `Workspace.owner_id`.
- Только owner изменяет workspace identity/settings. Non-owner может leave;
  owner сначала выполняет atomic ownership transfer.
- Owner/admin могут удалить другого участника только в пределах server policy.
- Production lifecycle — deactivate/archive и restore. Hard delete не является
  пользовательской операцией и не входит в React/API contract.

### Transactions and boundary changes

- Ownership transfer, last-owner enforcement, invitation consume/revoke и
  lifecycle transitions используют row locks и одну application transaction.
- Create workspace/invitation использует idempotency key. Settings, membership,
  invitation и lifecycle mutations используют committed optimistic tokens.
- Switch принимает ожидаемый current workspace, проверяет active membership и
  возвращает committed session snapshot.
- После switch, leave или deactivate сервер выбирает deterministic fallback.
  Клиент выполняет hard boundary navigation и не переносит cache/drafts/deep
  links предыдущего workspace.
- Deactivate сохраняет Accounts, Imports, Rules, Ledger, Reports и файлы, но
  отзывает pending invitations, инвалидирует web session references и отключает
  workspace-bound Chat/integration state по согласованному atomic contract.

### Invitation and interaction policy

- Invitation credential хранится только как hash, не возвращается в list DTO и
  показывается один раз после создания.
- Public preview раскрывает только display name, role и expiry, использует
  `Cache-Control: no-store` и строгую referrer policy.
- Invalid, expired, revoked и replayed credentials имеют единый privacy-safe
  outcome.
- Rename и role save не требуют отдельного dialog. Revoke, remove, leave,
  ownership transfer и deactivate требуют explicit confirmation. Switch требует
  confirmation только при наличии dirty draft.
- Короткая workspace settings form (name/type/currency) не сохраняет draft
  между переходами и не блокирует navigation. При `409` она автоматически
  загружает authoritative snapshot и просит повторить изменение. Create panel
  остаётся защищён от случайного закрытия с dirty draft.

## Consequences

- Wave C начинается с characterization и policy-lock slice; runtime behavior
  меняется только в следующих vertical slices.
- Single-owner invariant должен быть защищён транзакционно, а не только
  `count → write` проверкой.
- Workspace switch является cache/session boundary для всех React features.
- Legacy public invitation adapter сохраняется до отдельного replacement gate.
- Existing SSR CSRF form-token contract остаётся действующим до удаления
  authenticated legacy routes. Versioned API использует `X-CSRF-Token`.
- Generic CRUD abstraction для Workspaces не вводится: directory, switching,
  settings, membership, invitation и lifecycle имеют разные authority и
  consistency contracts.

## References

- [`workspaces/README.md`](../../frontend/plan/workspaces/README.md)
- [`API_AND_STATE.md`](../../frontend/plan/workspaces/API_AND_STATE.md)
- [`VERTICAL_SLICES.md`](../../frontend/plan/workspaces/VERTICAL_SLICES.md)
- [`TEST_MANIFEST.md`](../../frontend/plan/workspaces/TEST_MANIFEST.md)
- [`DELETE_MANIFEST.md`](../../frontend/plan/workspaces/DELETE_MANIFEST.md)
