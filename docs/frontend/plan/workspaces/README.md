# Workspaces React migration audit

Статус: `audit/Slice 0 complete; D1–D14 accepted; Slice 1–4 production gates passed 2026-08-04; Slice 5 public invitation accept next`.

Этот временный child stage ведёт Stage 7 Wave C migration authenticated
workflow Workspaces. На этапе аудита production runtime не менялся. После
принятия решений реализован и проверен Slice 1: directory, create и explicit
workspace switch на `/app/workspaces` через versioned JSON API. Slice 2 добавил
target-scoped general settings и lifecycle impact read model. D1–D14 приняты
без отклонений и зафиксированы в
[`ADR-0006`](../../../architecture/decisions/0006-workspace-migration-policy.md).
Legacy cleanup остаётся запрещён до соответствующих replacement gates.

Расширенный Slice 3 browser gate закрыт на production build: keyboard-only
transfer/leave и dialog focus return, owner/admin/editor/viewer matrix, 200%
text scaling, reduced motion, stale recovery и прямые запрещённые мутации.
Ручной прогон со screen reader исключён из gate по продуктовому решению
2026-08-04; это не отменяет существующие semantic labels и автоматические
accessibility assertions. Legacy member/invitation surface пока сохраняется,
поскольку тот же SSR runtime обслуживает public accept Slice 5 и другие
legacy workspace actions.

## Граница аудита

Фактический workflow сейчас состоит из:

```text
React AppShell / legacy shell / profile / dashboard
  -> legacy GET /workspaces
  -> WorkspaceService + WorkspaceRepository
  -> Jinja index + cards + forms
  -> legacy POST mutations and redirects

public invitation link
  -> GET /workspaces/invitations/{token}
  -> login/signup return
  -> POST accept
  -> web session switches workspace
```

Источники: `src/app/features/workspaces/router.py`, `service.py`,
`repository.py`, `presentation/`, `src/app/templates/workspaces/`,
`frontend/app/shell/app-shell.tsx`, `src/app/features/users/router.py`.

Slice 1 зарегистрирован в `src/app/api/v1/router.py` и `frontend/app/routes.ts`:
`GET/POST /api/v1/workspaces`, `POST /api/v1/workspaces/{id}/select` и
`/app/workspaces`; Slice 2 добавляет `GET/PUT /api/v1/workspaces/{id}` и
`/app/workspaces/:workspaceId/settings`. Первый increment Slice 3 добавил
bounded member directory, inline role update и disable/reactivate на этой же
странице через `/api/v1/workspaces/{id}/members/*`. Второй increment реализовал
atomic ownership transfer и self-leave с committed session snapshot и hard
boundary reload. `/api/v1/session` остаётся источником
активного workspace, membership, capabilities и CSRF token
(`src/app/api/v1/session/*`). Slice 4 добавил authenticated invitation
administration в React settings: pending metadata, idempotent one-time-link
create и locked revoke. Public preview/accept остаётся hardened SSR bridge;
lifecycle mutations отсутствуют. React settings также показывает read-only
lifecycle impact.

## Материалы

- [INVENTORY.md](INVENTORY.md) — routes, redirects, templates, backend,
  transactions, consumers и подтверждённые security findings.
- [UX_AUDIT.md](UX_AUDIT.md) — существующая геометрия и UI Foundation reuse.
- [SLICE_01_DESIGN_SPEC.md](SLICE_01_DESIGN_SPEC.md) — принятый contract
  directory, create panel, switch, responsive и accessibility для Slice 1.
- [prototype/index.html](prototype/index.html) — standalone Mocha/Latte visual
  prototype и state variants; не подключён к runtime routes/API.
- [API_AND_STATE.md](API_AND_STATE.md) — предлагаемые routes, API/DTO/errors,
  state ownership, invalidation и conflicts.
- [VERTICAL_SLICES.md](VERTICAL_SLICES.md) — последовательность replacement
  slices и gates.
- [TEST_MANIFEST.md](TEST_MANIFEST.md) — существующее и необходимое покрытие.
- [DELETE_MANIFEST.md](DELETE_MANIFEST.md) — точный keep/delete map после gate.

## Краткое резюме текущей архитектуры

- `Workspace`, `WorkspaceMember`, `WorkspaceInvitation` и audit events —
  SQLAlchemy persistence в одном feature; workspace является FK-root для всех
  финансовых aggregates (`models.py`, `docs/domain/DOMAIN_MODEL.md`).
- SSR router одновременно обслуживает directory, create/update/switch,
  membership, invitation и public accept flow. `router.py` (416 строк),
  `service.py` (472) и `repository.py` (353) рассказывают несколько разных
  историй; React migration — естественная точка разделения application actors,
  но не основание для generic CRUD.
- Services владеют commits. Repository выполняет queries/flush. Большинство
  entity reads workspace-scoped; session resolution дополнительно проверяет
  active membership и `Workspace.is_active`.
- Web current workspace принадлежит `UserSession.current_workspace_id`; Chat
  выбирает workspace независимо через active `ChatIdentityBinding`.
- Permission matrix server-owned и включает `owner`, `admin`, `editor`,
  `uploader`, `analyst`, `viewer`. Только owner управляет settings; owner/admin
  управляют invitations/members с дополнительными role guards.
- Lifecycle workspace не реализован: поля `is_active` и `archived_at` есть, но
  routes/use cases deactivate/archive/restore/delete отсутствуют. Transfer и
  leave теперь принадлежат `application/ownership.py`, а не lifecycle actor.

## Принятые решения

### D1. Scope первого React slice

**Рекомендация:** первый production slice — read-only directory + explicit
switch + create; settings, members и invitations идут отдельными slices.
Public invitation accept не включать в первый authenticated slice.

Альтернативы: (a) перенести всю страницу одним большим slice; (b) начать только
с AppShell switcher. (a) объединяет разные authority/concurrency риски; (b)
оставляет две directory surfaces. Рекомендация раньше доказывает главную
workspace boundary и сохраняет управляемый rollback.

### D2. Canonical и historical URLs

**Рекомендация:** до общего Stage 7 routing cutover использовать
`/app/workspaces` и `/app/workspaces/:workspaceId/settings`; после replacement
gate `GET /workspaces?...` становится query-preserving `307` на
`/app/workspaces?...`. Legacy POST не перенаправлять.

Альтернатива: сразу сделать `/workspaces` SPA canonical. Это преждевременно
меняет принятый `/app/*` runtime ADR-0001 и глобальное routing decision.

### D3. Directory/settings information architecture

**Рекомендация:** directory отвечает за выбор и создание; отдельная settings
route — за identity, access, invitations и activity выбранного workspace.
Внутри settings использовать URL section (`section=general|members|invites|activity`)
или подмаршруты только после проверки реальной длины разделов.

Альтернатива: одна длинная страница как SSR сейчас. Она смешивает switching,
creation, access и audit, а deep link к конкретному решению отсутствует.

### D4. Personal и shared UX

**Рекомендация:** единая directory/record geometry, но capability- и
type-aware copy/sections. Personal workspace не получает отдельное приложение;
collaboration controls показываются только если политика типа их допускает.

Альтернатива: отдельные personal/shared screens. Это дублирует navigation и
state contracts без текущего доменного основания.

### D5. Role/capability policy первой миграции

**Рекомендация:** сохранить существующие шесть ролей и server policy без RBAC
редизайна: owner — settings и все non-owner members; admin — invitations и
regular members, но не admin/owner; editor/uploader/analyst/viewer — без member
administration. UI получает capabilities и reason codes, не вычисляет их.

Альтернатива: упростить до owner/admin/member/viewer. Это breaking domain change
для imports, reports, Chat и текущих memberships и требует отдельного решения.

### D6. Rename/type/default currency

**Рекомендация:** только authoritative owner может менять identity/settings;
mutation требует `expectedUpdatedAt`. Изменение default currency не конвертирует
историю и требует явного impact copy. Type остаётся metadata, пока не приняты
type-specific policies.

Альтернатива: разрешить admin rename. Тогда `owner_id` перестаёт отражать
существующую workspace-management authority.

### D7. Lifecycle и hard delete

**Рекомендация:** production UI поддерживает deactivate/archive и restore, но
никогда hard delete. Финансовые данные, raw imports, audit и provenance
сохраняются. Hard delete остаётся только контролируемой operational procedure,
если когда-либо будет отдельно спроектирована.

Альтернатива: delete пустого workspace. Текущие `ON DELETE CASCADE` уже могут
удалить financial/import/rule trees; доказанного полного blocker contract нет.

### D8. Ownership и last-owner

**Рекомендация:** закрепить ровно одного authoritative owner, согласованного с
`Workspace.owner_id`; transfer выполняется атомарно с row locks: recipient
становится owner, прежний owner — admin, все sessions/capabilities
ревалидируются. Owner не может leave/deactivate себя через member action до
transfer. Last-owner проверка должна быть constraint/locked use case, не
отдельный count-then-write.

Альтернатива: несколько owner memberships. Тогда нужно определить смысл
singular `owner_id`, concurrent last-owner policy и transfer semantics.

### D9. Leave/remove policy

**Рекомендация:** non-owner может leave с confirmation; owner — только после
transfer. Owner/admin remove другого участника; self-remove через admin action
запрещён. Leave/remove деактивирует membership и инвалидирует workspace-bound
Chat bindings/states.

Альтернатива: не включать leave в Wave C. Это сохраняет текущую невозможность
самостоятельно прекратить shared access.

### D10. Active workspace после switch/leave/deactivate

**Рекомендация:** server выбирает deterministic fallback из active memberships
и возвращает полный committed session snapshot. Browser делает hard boundary
navigation/reload на safe collection route; entity deep links и drafts старого
workspace не переносятся. Если fallback отсутствует, создаётся не silently на
read, а через отдельный explicit onboarding/recovery outcome.

Альтернатива: сохранить текущий silent fallback/auto-create в session resolver.
Это делает GET side-effectful и скрывает lifecycle consequence.

### D11. Invitation accept и token privacy

**Рекомендация:** оставить отдельную public/authenticated bridge route в первом
authenticated migration; public preview раскрывает только workspace display
name, role и expiry. Response получает `Cache-Control: no-store` и strict
`Referrer-Policy`; token никогда не попадает в API list/DTO/log copy. Accept
использует locked compare-and-consume и одинаковый safe error для invalid,
expired, revoked и replayed credentials.

Альтернатива: сразу React public route. Это затрагивает ещё не принятое решение
о public/auth presentation и SPA fallback вне `/app`.

### D12. Deactivation blast radius

**Рекомендация:** одна locked application transaction устанавливает inactive,
revokes pending invitations, disables workspace integration/chat bindings,
invalidates pending conversation states и пересаживает web sessions на
fallback. Accounts/imports/rules/ledger/reports и файлы сохраняются, но новые
reads/writes через обычный context запрещены до restore.

Альтернатива: изменить только `Workspace.is_active`. Тогда внешние bindings и
pending credentials остаются необъяснимо активными.

### D13. Concurrency и idempotency

**Рекомендация:** `updatedAt`/status snapshots для settings, members,
invitations, lifecycle и ownership; row locks для transfer, last-owner,
invitation consume/revoke и deactivate. Create workspace/invitation принимает
`Idempotency-Key`; switch repeat-safe и дополнительно принимает
`expectedCurrentWorkspaceId` для stale tab detection.

Альтернатива: last-write-wins, как SSR сейчас. Она не даёт честного recovery и
не защищает concurrent invite/owner transitions.

### D14. Confirmation matrix и audit UI

**Рекомендация:** switch подтверждается только при зарегистрированном dirty
draft; rename/role save — без отдельного dialog; revoke invite, remove/leave,
ownership transfer, deactivate и restore-with-impact — explicit
`ConfirmationDialog`; successful mutations дают Toast. Activity остаётся
read-only bounded section, но не заменяет server audit/security logs.

Уточнение 2026-08-03: короткая settings form name/type/currency не сохраняет
draft и не блокирует navigation. После `409` она загружает актуальные значения
и просит повторить изменение; dirty create panel по-прежнему защищён.

Альтернатива: подтверждать каждую mutation. Это создаёт confirmation fatigue и
не выделяет действительно опасные transitions.

## Slice 0 policy lock

D1–D14 приняты 2026-08-03 без отклонений. Тем самым зафиксированы single-owner
semantics, включение leave/transfer и deactivate/restore в последовательность
Wave C, а также первоначальное сохранение public invitation SSR bridge.

Characterization gates для PostgreSQL invitation consume/revoke и last-owner
transitions, route-level CSRF/pre-lookup masking, session fallback и точного
deactivate impact закрыты. Найденные invitation races исправлены в Slice 4, а
last-owner races — в Slice 3; бывшие strict `xfail` теперь являются обычными
passing PostgreSQL regressions. Lifecycle replacement остаётся отдельным
последующим slice.

Фактический прогресс Slice 0 на 2026-08-03: CSRF и pre-lookup masking matrices,
session fallback/auto-create side effects, service-level concurrency failures и
deactivate impact contract зафиксированы. Minimal и rich owner-state browser
captures выполнены на 1440/920/390; rich mobile state воспроизводит 254 px
horizontal overflow из-за длинного member identity. Реальные PostgreSQL tests
доказывают две успешные accept, одновременно успешные accept/revoke и ноль
активных owners после встречного disable. Implementation-time verification
принятых контрактов остаётся gate соответствующих production slices.

Admin/editor/viewer browser matrix также завершена: 9 страниц на
1440/920/390 прошли без overflow и browser errors; фактическая видимость
invite/member/settings actions совпала с server policies. Из browser baseline
expanded create/edit, one-time invitation credential и invitation preview/error
states также завершены: 24 state/viewport комбинации прошли overflow/error gate.
Зафиксированы 40–42 px controls, pointer-inaccessible закрытие edit drawer и
сброс focus на `body` без live announcement после создания credential.

Тем самым Slice 0 characterization завершён. Недостижимый true no-workspace
screen не считается пропущенным screenshot: текущий context resolver создаёт
personal workspace на read, и это доказано characterization-тестом.

Обнаруженный при создании чистой browser БД repository blocker закрыт
2026-08-03. Ревизии `20260613_0003_phase4_ledger_posting.py` и
`20260613_0004_phase5_dedup_reparse.py` теперь добавляют PostgreSQL enum values
через Alembic `autocommit_block`, поэтому поздняя ревизия
`20260722_0017_confirmed_raw_dedupe_guard.py` может безопасно использовать
`confirmed` в predicate partial index. `alembic upgrade head` от пустой
одноразовой PostgreSQL БД и цикл `head -> 20260720_0016 -> head` прошли; revision
`20260802_0021`, оба enum values и partial unique index проверены SQL-запросом.
