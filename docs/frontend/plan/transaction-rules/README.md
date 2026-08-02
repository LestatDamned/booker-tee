# Transaction Rules React migration

Статус: `in progress`; аудит завершён 2026-08-01, решения D1–D7 приняты
2026-08-02, Slices 0–3 завершены 2026-08-02.

## Цель

Перенести authenticated SSR/HTMX workflow Transaction Rules в React, не меняя
владельца financial truth и не создавая второй rule engine.

```text
React /app/rules
  -> typed /api/v1/transaction-rules
  -> Transaction Rules application/domain
  -> workspace-scoped repositories
  -> RawTransaction suggestions
  -> existing React Import Review
```

Правило остаётся только источником предложения. Оно не создаёт confirmed
`Operation`, не обходит Import Review, dedupe, transfer policy или ledger
posting validation.

## Документы этапа

- [`INVENTORY.md`](INVENTORY.md) — фактические routes, behavior, models,
  consumers, данные и test coverage;
- [`UX_AUDIT.md`](UX_AUDIT.md) — оценка SSR UX/UI и композиция из UI Foundation;
- [`API_AND_STATE.md`](API_AND_STATE.md) — application/API contract, state
  ownership, validation и concurrency;
- [`VERTICAL_SLICES.md`](VERTICAL_SLICES.md) — последовательность реализации и
  replacement gates;
- [`TEST_MANIFEST.md`](TEST_MANIFEST.md) — server, React и browser evidence;
- [`DELETE_MANIFEST.md`](DELETE_MANIFEST.md) — точный legacy delete/keep list.

## Implementation progress

Slice 0 contract hardening завершён 2026-08-02:

- read side стал side-effect free;
- domain validation и workspace-aware target resolver выделены явно;
- create больше не выполняет weak silent deduplication;
- update/lifecycle/delete получили stale guards и row locks;
- enable revalidates archived/inactive targets;
- delete policy защищена application count и DB-level `RESTRICT`;
- missing-only seeder сериализован workspace lock и не меняет user rules;
- caller-owned Import Review/Chat transaction boundary сохранён;
- matching/winner semantics не менялись;
- migration `20260802_0021` проверена upgrade/downgrade и PostgreSQL tests.

Slice 1 read-only directory завершён 2026-08-02:

- добавлен workspace-scoped `GET /api/v1/transaction-rules` с SQL search,
  category/status filters, counts, stable ordering и bounded pagination;
- API возвращает полный read meaning правила, direct raw suggestion usage,
  server-owned capabilities и active/current-archived references;
- `/app/rules` доступен как прямой pre-cutover React route с runtime Zod
  validation, URL-owned state, responsive table/mobile list и stable anchors;
- viewer получает полный read projection без mutation controls;
- empty-directory browser audit прошёл 9/9 комбинаций 1440/920/390 ×
  Mocha/Latte/test theme без overflow или console/request errors;
- canonical navigation и Categories links остаются на SSR до Slice 6.

Slice 2 create и explicit seed defaults завершён 2026-08-02:

- `POST /api/v1/transaction-rules` использует обязательный Idempotency-Key;
  детерминированный workspace-scoped id безопасно повторяет точный payload и
  отвергает reuse ключа с другим правилом;
- создание доступно в правой `WorkbenchPanel`: полный SSR-equivalent набор
  полей, preview, client/server validation, pending, сохранение draft,
  подтверждение закрытия, Toast и stable anchor;
- `POST /api/v1/transaction-rules/seed-defaults` вызывается только после
  подтверждения, создаёт только отсутствующее и возвращает truthful counts;
- viewer mutations закрыты server permission dependency, а UI не показывает
  create/seed controls;
- SSR create/seed остаются рабочими до cutover Slice 6.
- browser geometry audit прошёл 9/9 комбинаций 1440/920/390 ×
  Mocha/Latte/test theme; отдельный interaction audit create drawer,
  dirty-close и seed confirmation прошёл 3/3 без выполнения mutations.

Slice 3 edit завершён 2026-08-02:

- authoritative edit snapshot загружается отдельным workspace-scoped API;
- `PUT` требует `expectedUpdatedAt`, stale update возвращает typed `409`;
- одна `ExpansionPanel`-форма раскрывается непосредственно под desktop row или
  mobile record, возвращает фокус и подтверждает потерю dirty draft;
- текущие archived targets остаются видимыми и сохраняемыми, но новая
  unavailable/foreign target не принимается;
- committed summary заменяет строку без изменения URL filters/page, результат
  подтверждается Toast; dormant поля update не перезаписывает.

Следующий этап — Slice 4: enable/disable с явным влиянием только на будущий
matching и без скрытой перезаписи существующих Import Review suggestions.

## Краткий вывод аудита

Существующий rule engine уже разделён на management, application, queries и
чистые matching/suggestion policies. Его нельзя переписывать ради JSX. Однако
SSR boundary недостаточен как React API и содержит несколько контрактных
дефектов:

1. JSON CRUD API для правил отсутствует; OpenAPI содержит legacy HTML/form
   operations `/rules*`.
2. GET `/rules` вызывает `CategoryService.list_or_seed_defaults()` и выполняет
   commit, то есть read имеет side effect.
3. Interactive create считает правилом-дублем только `pattern + category_id` и
   молча возвращает существующую запись, даже если direction, property, amount
   или operation type отличаются.
4. Update/toggle/delete работают last-write-wins; `updated_at` уже существует,
   но не используется как optimistic token.
5. Category и Property workspace ownership проверяются; dormant `account_id`
   такой проверки не имеет.
6. Amount range не запрещает отрицательные границы и `min > max`; слишком
   длинный pattern молча обрезается, а длинное name может дойти до DB error.
7. Hard delete разрешён для активного и уже применённого правила. FK обнуляет
   `RawTransaction.suggested_by_rule_id`, хотя suggestion snapshot остаётся в
   payload; это может изменить restored review status после undo.
8. Seeder обещает не менять пользовательские правила, но переводит найденное
   совпадение в `auto_apply`.
9. Термин `auto_apply` в UI звучит как автоматическое проведение. Фактически он
   лишь даёт полностью предзаполненной строке быстрый confirm; ledger posting
   всё равно проходит server validation и явное действие пользователя.
10. SSR list загружает все правила workspace и фильтрует в Python; pagination —
    только увеличение `limit` до 1000.

## Финансовые и security invariants

Во всех slices обязательны:

- every rule/read/write/target lookup workspace-scoped;
- category, property и возможный account target разрешаются сервером, а не из
  browser payload;
- archived/inactive references не становятся новыми активными targets молча;
- rule application меняет только suggestion state допустимого unlinked raw row;
- parser, mapping и rule engine не создают confirmed ledger records;
- `auto_apply` не означает silent confirmation;
- Income/Expense/Transfer и `affects_profit` повторно определяются и проверяются
  ledger/import application boundary;
- transfer остаётся `affects_profit=false`, требует разные accounts и не входит
  в profit/ROI;
- duplicate/review/status/idempotency guards Import Review не ослабляются;
- delete не удаляет raw source, suggestion evidence или confirmed operations;
- expected conflicts возвращают typed `409/422`, private payload не попадает в
  response/logs.

## Принятые решения

### D1. Routes и deep links

Предлагается:

- canonical browser route: `/app/rules`;
- React Router route: `/rules` внутри SPA basename;
- API: `/api/v1/transaction-rules`;
- historical GET `/rules` после replacement gate становится query-preserving
  `307` redirect на `/app/rules`;
- anchors `#rule-<uuid>` сохраняются для Categories detail и старых bookmarks;
- legacy POST/HTMX routes не получают redirects и удаляются после cutover.

### D2. Lifecycle и hard delete

Предлагается сохранить двухсостоянийный lifecycle `active | disabled` без
искусственного archive status:

- disable — основное обратимое действие; оно влияет только на будущий matching
  и последующий явный `Apply rules`;
- существующие raw suggestions не очищаются скрыто;
- enable повторно валидирует current category/property/account targets;
- hard delete разрешён только disabled rule с нулём прямых
  `RawTransaction.suggested_by_rule_id` references;
- linked/used rule остаётся доступным для disable, но `canDelete=false` с
  blocker count/reason;
- delete использует `expectedUpdatedAt`, confirmation и authoritative response.

Причина строгой policy: текущий `ON DELETE SET NULL` сохраняет raw row, но
разрывает provenance и меняет `restored_review_status_after_unlink()`.

### D3. Concurrency

Update, enable, disable и delete передают `expectedUpdatedAt`. Stale snapshot
возвращает `409 transaction_rule_*_conflict`; React предлагает authoritative
reload и явный retry. Финансовые/rule mutations не optimistic.

### D4. Поля первой React-версии

Write form сохраняет фактически доступные в SSR поля: name, pattern, match type,
direction, amount range, operation type, category, property и application mode.

`account_id`, `priority`, `auto_description`, `affects_profit` не получают новые
controls в migration scope: локальный read-only measurement показал `0`
non-default значений во всех 1649 правилах. Application update обязан сохранять
их без перезаписи, а pre-cutover production measurement — остановить cutover,
если обнаружит реальные non-default rows. `account_id` при этом всё равно
получает workspace validation на server boundary.

Это не удаляет dormant schema и не объявляет её новым product contract.

### D5. Seed defaults

Seeder становится отдельной explicit mutation:

- создаёт только отсутствующие категории/правила;
- никогда не меняет mode, active state или поля существующего user rule;
- возвращает counts `createdRules`, `existingRules`, `createdCategories`;
- повтор безопасен, concurrent duplicate защищён server/DB contract;
- confirmation честно называет объём и последствия.

### D6. Matching semantics

Migration фиксирует, но не меняет текущий winner algorithm:

```text
active workspace rules
  -> workspace/account/direction/absolute amount/text match
  -> specificity score: category, property, operation type, account, amount
  -> repository order priority/created_at resolves equal score
```

Exact match и длинный pattern сейчас не получают дополнительный вес. Улучшение
ranking — отдельный domain stage с characterization tests, не часть React
migration.

### D7. URL list state

Предлагается server pagination и URL ownership:

```text
q, category_id, status, page, page_size
```

Default `status=all`, `page=1`, `page_size=50`; допустимые page sizes bounded.
Старый `limit` принимается только как compatibility input и нормализуется в
новый URL. Hash target не является selection state и не открывает editor
автоматически.

## Не входит в scope

- новый rule language, regex, AND/OR groups или visual query builder;
- bulk edit/reorder и drag-and-drop priority;
- автоматическая ретрокатегоризация confirmed history;
- silent confirmation/posting;
- изменение Import Review queue, dedupe или transfer architecture;
- schema-driven CRUD/form generator;
- перенос Chat rule flow в browser;
- удаление dormant DB columns без отдельного migration decision.

## Approval record

D1–D7 приняты пользователем 2026-08-02. Slices 0–3 завершены; legacy SSR
остаётся canonical до replacement gate Slice 6.
