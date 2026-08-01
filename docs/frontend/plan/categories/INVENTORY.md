# Categories observed behavior inventory

Статус: audit snapshot для планирования; проверено по коду, тестам и локальному
SSR browser flow 2026-08-01.

## Текущий runtime flow

```text
GET /categories
  -> get_current_workspace_context
  -> CategoryService.list_management_rows()
  -> seed missing system/default categories + commit
  -> CategoryPagePresenter
  -> templates/categories/index.html

GET /categories/{id}
  -> CategoryService.get_detail()
  -> confirmed Operations + profit-only summary + linked Rules
  -> CategoryPagePresenter
  -> templates/categories/detail.html

POST create/update/archive/restore/delete
  -> CSRF + require_financial_write_context
  -> CategoryService
  -> workspace-scoped repositories
  -> commit
  -> 303 redirect или SSR error re-render
```

`src/app/main.py` включает HTML router напрямую. Versioned Categories API
отсутствует; generated OpenAPI содержит legacy HTML/form operations
`/categories*`, а не typed JSON workflow.

## Архитектурная оценка

- `CategoryRepository` содержит workspace-scoped queries и persistence writes;
  ownership boundary в entity lookup соблюдён;
- `CategoryPagePresenter` действительно готовит SSR view state и не мутирует
  финансовые данные — после cutover он удаляется, а не переиспользуется в API;
- `CategoryService` сейчас объединяет четыре причины изменения: bootstrap seeds,
  reference lookup для consumers, directory/detail reads и management
  mutations/transactions;
- `get_detail()` напрямую координирует Ledger, Reports summary и Rules и
  возвращает ORM-rich objects, что подходит legacy presenter, но не JSON
  contract;
- commits спрятаны внутри service methods, а некоторые callers используют
  `ensure_*` внутри своей транзакции. При эволюции нельзя сломать различие
  commit-owning и caller-owned workflows;
- progressive feature architecture не требует переписывать весь service:
  новые API DTO/readers/commands добавляются по пользовательским outcomes, а
  стабильные `list_active`/`ensure_system` consumers сохраняются.

Focused clean-architecture вывод: router должен остаться HTTP adapter,
application actors — владеть directory/detail/mutations, repository — только
queries, React — только prepared state/interaction. Универсальный reference CRUD
слой между Categories и Properties не обоснован.

## Routes и authority

| Route | Поведение | Authority |
| --- | --- | --- |
| `GET /categories?view=&recent_category_id=` | seeds defaults, filters active/archive/system/all, recent feedback | authenticated workspace context |
| `GET /categories/{id}?date_from=&date_to=&currency=&type=&return_to=` | summary, все matching confirmed operations и rules | workspace-scoped category lookup; safe return только `/app/reports` |
| `POST /categories` | create active custom category | financial write + CSRF + case-insensitive name check |
| `POST /categories/{id}` | update name/kind/notes | financial write + CSRF; system forbidden |
| `POST /categories/{id}/archive` | `is_active=false` | financial write + CSRF; system forbidden |
| `POST /categories/{id}/restore` | `is_active=true` | financial write + CSRF; system forbidden |
| `POST /categories/{id}/delete` | hard delete archived custom category при текущих partial blockers | financial write + CSRF; system forbidden |

Template скрывает mutations по `workspace_permissions.can_write_financial_data`.
Будущий API должен использовать общий `get_api_request_context` и
`require_api_financial_write_context`, чтобы read/write policy была explicit.

## Persistence и seeds

`Category` содержит `id`, `workspace_id`, optional `parent_id`, `name`, `kind`,
`is_active`, `is_system`, optional `system_key`, `sort_order`, optional `notes`,
`created_at`, `updated_at`.

Kinds: `income`, `expense`, `transfer`, `adjustment`, `mixed`.

System seeds: `uncategorized`, `transfer`, `adjustment`, `refund`, `duplicate`,
`ignore`, fallback `income`, fallback `expense`, `rent`. Они всегда active,
immutable для пользователя и переименовываются/исправляются при ensure.

Default custom seeds покрывают типовые income/expense choices. Workspace типа
`property_management` получает дополнительные rental/property categories.
Directory GET сегодня является write-on-read: восстанавливает missing defaults
и commit-ит.

`parent_id` и `sort_order` существуют в persistence, но пользовательского tree
или manual ordering workflow нет. Их нельзя случайно экспонировать как новый
scope.

## Validation и lifecycle

- name/notes схлопывают whitespace, blank notes становятся `None`;
- name required; уникальность case-insensitive внутри workspace;
- DB max name 255, но SSR form/service не дают стабильного max-length field
  error;
- custom kind можно менять даже при linked operations/rules;
- archive не меняет linked operations, raw suggestions или rules;
- active pickers используют `list_active`, поэтому archived category исчезает;
- existing active rule не проверяет `category.is_active` при application и может
  продолжить предлагать archived category;
- `updated_at` существует, но SSR mutations last-write-wins;
- system category нельзя edit/archive/restore/delete.

## Detail и финансовая семантика

Detail принимает ISO dates, трёхбуквенную currency и только flow `income` или
`expense`. Direct route использует default currency workspace. `return_to`
разрешён только для local `/app/reports...`, что закрывает open redirect.

Repository читает confirmed operations по category/filter. Summary считает
только operations с `affects_profit=true` через существующую чистую Reports
policy. Transfer и adjustment могут присутствовать в общем списке, но не должны
влиять на income/expense/profit. Row total суммирует MoneyEntry через `Decimal`.

Текущий detail не имеет pagination: все matching operations и все linked rules
загружаются и рендерятся одним response.

## Пользовательские сценарии

1. Просмотреть active custom categories по kind.
2. Переключить archive/system/all view.
3. Создать category, сохранить draft при server error и найти recent row.
4. Открыть detail из directory или counts.
5. Открыть detail из Reports, сохранив period/currency/back context.
6. Понять category kind/status/notes и counts.
7. Посмотреть profit summary и confirmed operations.
8. Перейти к связанному Transaction Rule.
9. Изменить custom name/kind/notes.
10. Архивировать/восстановить custom category.
11. Удалить неиспользованную archived custom category.
12. Работать read-only без mutation controls.

## Финансовые и security invariants

1. Category описывает смысл операции, но не является источником денег.
2. `Operation.type` и `affects_profit` остаются server-owned; `CategoryKind` их
   не переопределяет.
3. Transfer всегда `affects_profit=false` и не попадает в income/expense/profit.
4. Summary использует только confirmed profit operations и одну currency.
5. Archive не удаляет и не переписывает Operation/RawTransaction/Rule/history.
6. Archived category не предлагается в active manual/review/rule target pickers.
7. System categories и `system_key` нельзя менять пользовательским API.
8. Все reads, counts, references и mutations workspace-scoped.
9. Browser отображает capabilities/blockers сервера, а не выводит policy из
   status, role или counts.
10. Duplicate name check остаётся case-insensitive и workspace-scoped.
11. Raw import suggestions и parser data не теряются из-за lifecycle/delete.
12. Committed server snapshot — единственный mutation success source.

## Найденный delete gap

`delete_archived_custom()` проверяет только:

- confirmed Operations через `count_operations_by_category()`;
- все Transaction Rules через `count_rules_by_category()`.

Но FK без `ON DELETE SET NULL` также существуют у Operations других statuses,
`RawTransaction.suggested_category_id`, child `Category.parent_id` и Rules.
Следовательно, UI может показать delete, после чего flush/commit получит DB
integrity error. Новый contract обязан иметь полный dependency query и tests;
клиентские counts не могут быть authority.

## Тесты

### Replacement-only SSR observations

- `tests/features/categories/test_categories.py`: presenter state, URLs,
  filtering, form/lifecycle redirects и часть service policy;
- category blocks в
  `tests/features/reference_data/test_reference_templates.py`: cards, recent
  feedback, create/edit draft, detail operations/rules и lifecycle rendering.

### Сохраняемые domain/integration consumers

- category seed, normalization, uniqueness и workspace service tests;
- Manual Ledger reference resolution and active options;
- Import Review classification/category creation and compatibility;
- Reports filter/aggregate/currency/transfer tests;
- Transaction Rules matching, target resolution, suggestions and templates
  до их собственного cutover;
- Chat manual/review/dashboard category selection tests;
- model/migration/FK tests.

Focused characterization run на audit snapshot: `61 passed` для Categories,
reference templates, Manual Ledger references и Reports/API suites.

### Недостающее покрытие

- versioned API auth/permission/CSRF/404/409/422 contracts;
- full dependency blockers для delete;
- archive + active-rule policy;
- concurrency для update/lifecycle/delete;
- max length и field errors;
- paginated detail read model и workspace isolation;
- React URL/form/focus/read-only/retry/detail tests;
- both-theme responsive browser acceptance.

## Runtime consumers, которые нужно сохранить

| Consumer | Использование |
| --- | --- |
| Ledger models/application/repository | `Operation.category_id`, posting fallback/system transfer, filters |
| Manual Ledger API/React | active category references and list filters |
| Import Review API/React | kind-aware active choices, inline create, suggestions/posting |
| Reports repository/API/React | category filter, aggregates, archived labels, drill-down link |
| Transaction Rules | category target, matching suggestion, active rule references |
| Raw Transactions | `suggested_category_id` and preserved review evidence |
| Accounts detail/correction | category facts on operation records |
| Chat integrations | manual/review selection and dashboard summaries |
| Workspace/bootstrap | ownership relationship and default/system seeds |
| migrations/models | enums, FKs, indexes and historical integrity |
