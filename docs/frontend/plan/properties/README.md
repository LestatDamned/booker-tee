# Properties React migration

Статус: `completed 2026-08-01`; Slices 01–05 и SSR cleanup завершены.

Этот child stage описывает первую задачу Wave B: замену authenticated SSR
страницы `/properties` на React workflow `/app/properties` и versioned JSON API.
Согласованные решения ниже являются контрактом следующих slices.

## Цель

Перенести реестр объектов без изменения их финансового смысла:

```text
React /app/properties
  -> typed /api/v1/properties
  -> Property application/service boundary
  -> workspace-scoped repository
  -> Property persistence model
```

Property остаётся необязательной аналитической привязкой операции. Экран не
вычисляет property ROI, не меняет transfer semantics и не удаляет исторические
связи.

## Материалы stage

- [INVENTORY.md](INVENTORY.md) — фактическое SSR-поведение, код, API, тесты,
  consumers и финансовые инварианты;
- [UX_AUDIT.md](UX_AUDIT.md) — geometry baseline, UX/UI-аудит и reuse matrix;
- [DELETE_MANIFEST.md](DELETE_MANIFEST.md) — точный cleanup после replacement
  gate;
- [01_DIRECTORY_AND_READ_CONTRACT.md](01_DIRECTORY_AND_READ_CONTRACT.md) —
  workspace-scoped read API и React directory;
- [02_CREATE.md](02_CREATE.md) — создание объекта;
- [03_EDIT.md](03_EDIT.md) — редактирование существующего объекта;
- [04_LIFECYCLE.md](04_LIFECYCLE.md) — archive/restore и последствия для
  связанных workflows;
- [05_CUTOVER_AND_CLEANUP.md](05_CUTOVER_AND_CLEANUP.md) — canonical routing,
  replacement gate и удаление SSR presentation.

## Предлагаемый пользовательский контракт

- одна collection-workbench страница с активными и выведенными из активного
  использования объектами;
- URL хранит applied search/status view; form drafts и pending state остаются
  локальными;
- создание открывается в `WorkbenchPanel`, редактирование — в
  `ExpansionPanel` под записью;
- committed mutation обновляет строку authoritative API snapshot и даёт Toast;
- archive/restore не являются optimistic и не удаляют объект;
- read-only участник видит реестр и понятное объяснение недоступности mutations;
- page-level и, если принято решение D4, row-level переход в Reports сохраняет
  property filter.

## Принятые решения

### D1. Dormant status `inactive` — принято 2026-08-01

Модель и PostgreSQL enum допускают `active | inactive | archived`, но текущий
service создаёт только `active` и переключает только `active <-> archived`.
SSR presenter ошибочно показывает `inactive` как active. В локальной dev-БД
строк `inactive` не найдено, но это не доказывает состояние всех окружений.

Принято: migration `20260801_0019` детерминированно нормализует legacy
`inactive` в `archived` и заполняет отсутствующий `archived_at` из `updated_at`.
Python/API/browser lifecycle двухсостояний: `active | archived`; API не выполняет
silent coercion. PostgreSQL enum label остаётся неиспользуемым техническим
артефактом, потому что удаление enum value небезопасно и не нужно контракту.

### D2. Archive и активные transaction rules — принято 2026-08-01

Сейчас archive убирает объект из active picker, но `get_for_workspace()` всё
ещё принимает archived объект. Уже существующее active transaction rule может
продолжить предлагать его новым импортированным строкам.

Принято: не отключать правила автоматически и не менять
posting policy скрыто. Lifecycle response должен честно показать impact/capability,
а confirmation copy — сообщить, что история сохраняется и связанные правила не
изменяются. Автоматическое отключение правил требует отдельного domain-решения.

### D3. Concurrency

Принято: использовать существующий `updated_at` как optimistic token для
update/archive/restore и отвечать `409 property_update_conflict` либо
`property_lifecycle_conflict` при stale snapshot. SSR сейчас использует
last-write-wins, но React/API conventions уже закрепили явный conflict recovery.

### D4. Переход в Reports

Принято: сохранить page-level действие «Отчёты» и добавить тихое действие
записи на `/app/reports?property_id=<uuid>`. Reports уже валидирует этот filter;
ссылка не переносит расчёты в Properties.

## Не входит в scope

- detail page, CRM/lease/tenant/vacancy workflow;
- оценка стоимости объекта или asset management;
- property-specific accounting engine или расчёт ROI в browser;
- hard delete Property;
- изменение transfer, reporting или rule semantics без отдельного решения;
- универсальный CRUD/schema renderer.

## Последовательность

```text
01 read contract + directory
  -> 02 create
  -> 03 edit
  -> 04 lifecycle
  -> 05 replacement gate + cutover + cleanup
```

Текущее положение: Slices 01–05 completed. `/app/properties` — canonical React
workflow; historical `GET /properties` является query-preserving compatibility
redirect. Legacy mutable presentation stack удалён после replacement gate.

Каждый slice прошёл `application/API -> typed state -> UI -> tests`.

## Общий exit gate

- согласованы D1–D4;
- canonical AppShell и оставшийся legacy shell ведут на `/app/properties`;
- `GET /properties?...` — query-preserving compatibility redirect;
- API проверяет session, workspace read/write permission, CSRF и stale state;
- active reference consumers Manual Ledger, Import Review, Accounts, Reports,
  Transaction Rules и Chat сохраняют поведение;
- React tests покрывают directory, URL state, create/edit/lifecycle,
  read-only, errors, focus и draft preservation;
- browser flow проходит в Mocha и Latte на 1440/920/390 без overflow и ошибок;
- SSR router/presenter/template/property-only CSS/JS/test assertions удалены;
- каждый сохранённый legacy consumer назван в delete manifest.

## Completion

Canonical React Properties реализует directory, URL search/status view,
create/edit и archive/restore через versioned API с workspace, permission,
CSRF и optimistic-concurrency authority на сервере. Historical GET сохраняет
query; legacy mutations отсутствуют. SSR router/presenter/template, его тесты и
property-only global assets удалены. Полный фактический check/cleanup/measurement
record находится в [Slice 05](05_CUTOVER_AND_CLEANUP.md).
