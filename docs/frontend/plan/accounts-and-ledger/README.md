# Stage 07 / Wave A: Accounts And Account Ledger

Статус: active; Slices 01–03 completed.

Этот child stage мигрирует authenticated workflow счетов:

```text
список счетов
  -> создание счета
  -> карточка счета
  -> фильтрация и просмотр проводок
  -> настройки / archive / restore
  -> correction разрешенных полей imported operation
```

React и versioned JSON API становятся presentation adapters над существующими
accounts/ledger application и domain rules. План не меняет accounting shape,
балансовую формулу, posting, Manual Ledger или Import Review.

## Связанные документы

- [`INVENTORY.md`](INVENTORY.md) — наблюдаемое SSR-поведение, границы данных,
  geometry baseline, security/invariants и consumer/delete manifest.
- [`01_ACCOUNT_LIST_AND_CREATE.md`](01_ACCOUNT_LIST_AND_CREATE.md) — список,
  агрегированные балансы и создание счета.
- [`02_ACCOUNT_DETAIL_LEDGER.md`](02_ACCOUNT_DETAIL_LEDGER.md) — карточка счета,
  фильтры, пагинация и проводки.
- [`03_ACCOUNT_MANAGEMENT.md`](03_ACCOUNT_MANAGEMENT.md) — изменение настроек,
  detail-level management и завершение lifecycle cleanup; list-level
  archive/restore уже доставлены в Slice 01.
- [`04_IMPORTED_OPERATION_CORRECTION.md`](04_IMPORTED_OPERATION_CORRECTION.md) —
  correction разрешенных полей подтвержденной импортированной операции.
- [`05_CUTOVER_AND_CLEANUP.md`](05_CUTOVER_AND_CLEANUP.md) — canonical links,
  redirects, browser gate и удаление legacy presentation.

## Почему это следующий child stage

- Stage 07 ставит account detail/ledger следующим core financial workflow после
  Imports.
- Счета связывают Manual Ledger, Imports, reports и dashboard.
- Slice 01 уже переключил React shell на `/app/accounts` и заменил list/create.
- Focused aggregate projection устранил прежний per-account full-ledger N+1.
- Активный ledger-refactoring сознательно отложил account projections и legacy
  cleanup до React account cutover.
- После replacement gate можно удалить крупный Jinja/HTMX presenter stack,
  вместо Pydantic-полировки временных ViewModels.

Оценка сложности: средне-высокая, около `7/10`.

Ориентир для одного разработчика, включая API, React, тесты, realistic browser
flow и cleanup: `14–22` focused engineering days. Это planning range, не срок
или SLA.

## Порядок slices

| Порядок | План                                                                         | Статус    | Пользовательский результат                          |   Оценка |
| ------- | ---------------------------------------------------------------------------- | --------- | --------------------------------------------------- | -------: |
| 1       | [`01_ACCOUNT_LIST_AND_CREATE.md`](01_ACCOUNT_LIST_AND_CREATE.md)             | completed | Видит счета и безопасно создает новый               |  3–4 дня |
| 2       | [`02_ACCOUNT_DETAIL_LEDGER.md`](02_ACCOUNT_DETAIL_LEDGER.md)                 | completed | Видит баланс и находит нужные проводки              | 4–6 дней |
| 3       | [`03_ACCOUNT_MANAGEMENT.md`](03_ACCOUNT_MANAGEMENT.md)                       | completed | Меняет настройки и управляет active state           |  2–3 дня |
| 4       | [`04_IMPORTED_OPERATION_CORRECTION.md`](04_IMPORTED_OPERATION_CORRECTION.md) | planned   | Исправляет classification импортированной операции |  2–3 дня |
| 5       | [`05_CUTOVER_AND_CLEANUP.md`](05_CUTOVER_AND_CLEANUP.md)                     | planned   | Использует только React Accounts                    | 3–6 дней |

Imports child stage прошёл full Playwright audit и завершён. Следующий срез —
Slice 04, correction разрешённых полей imported operation.

## Канонические маршруты на время Stage 07

```text
/app/accounts
/app/accounts/:accountId
```

Фильтры detail хранятся в query string. Выбранная/раскрытая проводка может
храниться как `operation_id`, если interaction test подтверждает необходимость
восстановления через Back/Forward и deep link.

После replacement соответствующего экрана historical GET становятся
query-preserving compatibility redirects:

```text
/accounts
/accounts/{account_id}
```

Historical HTML POST/HTMX endpoints удаляются после mutation gates. Временный
`/app` prefix снимается только общим Stage 07 routing cutover.

## Общая application/API boundary

```text
React route
  -> focused typed API client
  -> /api/v1/accounts/*
  -> account directory / ledger / management application actor
  -> workspace-scoped repository
```

Предполагаемый JSON API:

```text
GET  /api/v1/accounts
POST /api/v1/accounts

GET  /api/v1/accounts/{account_id}
PUT  /api/v1/accounts/{account_id}
POST /api/v1/accounts/{account_id}/archive
POST /api/v1/accounts/{account_id}/restore

PUT  /api/v1/accounts/{account_id}/operations/{operation_id}/review-fields
```

Имена application DTO/actors уточняются по существующей структуре, но границы
фиксированы:

- list read возвращает account summaries одной focused query/projection;
- detail read возвращает account facts, authoritative balance, paginated
  movements, filter options и capabilities;
- account mutations проходят через один application transaction owner;
- imported operation correction переиспользует
  `ImportedOperationReviewUseCase`, optimistic operation version и server
  policy;
- API schemas не используют ORM, Jinja ViewModels или HTML fragments.

## State ownership

Backend владеет:

- workspace ownership и permission checks;
- persisted account fields и active state;
- authoritative balance из confirmed `MoneyEntry`;
- movement source/type/status, transfer route facts и account-relative amount;
- operation/account capabilities и stable blocking reason codes;
- optimistic/stale-state checks;
- допустимость imported operation correction.

URL владеет:

- account identity;
- `date_from`, `date_to`, `source`, `type`, `status`, `category_id`,
  `property_id`, `search`, `page`, `per_page`;
- optional target operation context, если он нужен deep-link UX.

Feature-local React state владеет:

- create/settings/correction drafts;
- раскрытыми panels/dialogs;
- pending, focus и recoverable error state;
- последним committed row/account snapshot до route revalidation.

Глобальный client store или cache dependency не добавляется без доказанной
проблемы.

## Общие API-правила

- Money передается decimal string, currency — отдельно.
- Reads side-effect free: detail GET не seed-ит categories и не делает commit.
- List не загружает paginated movements каждого счета.
- Server возвращает facts/capabilities/reason codes, не русские labels, CSS
  tones или browser URLs.
- Mutations не optimistic и возвращают smallest truthful committed snapshot.
- Account update получает явный stale-state guard по текущему `updatedAt` либо
  эквивалентному application token; конфликт возвращает `409`.
- Archive/restore повторно проверяют expected active state и текущую policy.
- Imported correction использует `expectedVersion` операции и возвращает `409`
  для stale или недопустимого transition.
- `404` не раскрывает существование account/operation другого workspace.
- API не публикует account fingerprint, external reference или другие
  persistence-only identifiers без отдельной пользовательской потребности.

## Общие invariants

1. Каждый account, operation, category и property lookup workspace-scoped.
2. Viewer может читать счета и ledger, но не получает mutation capabilities.
3. Баланс равен `initial_balance + confirmed MoneyEntry`; filters изменяют
   список/количество совпадений, но не authoritative current balance.
4. Transfer меняет баланс участвующих счетов, но не влияет на profit.
5. Money остается `Decimal`/`Numeric`; browser не вычисляет баланс.
6. Архивный счет остается видимым и исторически читаемым.
7. Account create/update/archive/restore требуют financial-write permission.
8. Correction разрешен только для confirmed `BANK_PDF` operation, связанной с
   текущим account.
9. Correction меняет только description/category/property, сохраняет posting и
   проверяет optimistic version.
10. Read endpoints не создают default categories и не мутируют lifecycle.

## Общий exit gate

Child stage завершен только когда:

- list и detail работают через React и `/api/v1`;
- canonical shell и все runtime links ведут в `/app/accounts...`;
- workspace isolation, capabilities, balances и mutation concurrency доказаны
  server tests;
- React tests покрывают URL state, drafts, errors, focus и accessibility;
- realistic browser flow проходит на `1440`, `920` и `390`;
- historical GET только redirect, legacy POST/HTMX endpoints отсутствуют;
- account Jinja presenters/templates и replacement-only tests удалены;
- account-specific legacy CSS удален после consumer search;
- оставшиеся shared legacy selectors имеют именованных runtime consumers;
- ledger/domain posting не переписан ради React.
