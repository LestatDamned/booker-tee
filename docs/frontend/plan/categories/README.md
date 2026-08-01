# Categories React migration

Статус: `active 2026-08-01`; D1–D5 приняты, Slices 01–05 completed,
Slice 06 next.

Этот child stage описывает вторую задачу Wave B: замену authenticated SSR
маршрутов `/categories*` на React directory `/app/categories`, React detail
`/app/categories/:categoryId` и versioned JSON API.

## Почему нужен отдельный план

Categories — не обычный CRUD-справочник. Категория:

- отвечает на вопрос, почему деньги пришли или ушли;
- используется Manual Ledger, Import Review, Reports, Transaction Rules и Chat;
- имеет immutable системные записи и workspace-specific default seeds;
- определяет совместимость options в Import Review через `CategoryKind`;
- открывается из Reports с периодом, валютой и безопасным возвратом;
- может быть архивирована или удалена только с учётом всех ссылок.

Перенос «по аналогии с Properties» полезен на уровне UI/API conventions, но не
заменяет отдельный финансовый и lifecycle contract.

## Материалы stage

- [INVENTORY.md](INVENTORY.md) — фактическое SSR-поведение, routes, persistence,
  tests, consumers и инварианты;
- [UX_AUDIT.md](UX_AUDIT.md) — observed geometry, UX/UI-аудит и reuse matrix;
- [API_AND_STATE.md](API_AND_STATE.md) — предлагаемый JSON contract и ownership
  browser/server state;
- [DELETE_MANIFEST.md](DELETE_MANIFEST.md) — legacy cleanup и replacement map;
- [01_DIRECTORY_AND_READ_CONTRACT.md](01_DIRECTORY_AND_READ_CONTRACT.md);
- [02_CREATE.md](02_CREATE.md);
- [03_DETAIL_DRILLDOWN.md](03_DETAIL_DRILLDOWN.md);
- [04_EDIT.md](04_EDIT.md);
- [05_LIFECYCLE_AND_DELETE.md](05_LIFECYCLE_AND_DELETE.md);
- [06_CUTOVER_AND_CLEANUP.md](06_CUTOVER_AND_CLEANUP.md).

## Целевой пользовательский контракт

- `/app/categories` показывает компактный searchable directory с views
  `active | archived | system` и количествами;
- system categories явно read-only и не смешиваются с пользовательскими;
- create и page-level edit открываются в общем `WorkbenchPanel` справа;
- `/app/categories/:categoryId` показывает identity, период/валюту, server-owned
  money summary, paginated confirmed operations и связанные rules;
- drill-down из Reports сохраняет `date_from`, `date_to`, `currency`, `type` и
  безопасный `return_to=/app/reports...`;
- mutations не optimistic: committed API snapshot заменяет локальную запись;
- archive/restore/delete используют capability и dependency facts сервера;
- viewer видит тот же directory/detail без mutation controls и с явным
  read-only объяснением;
- direct detail сохраняет default currency workspace, а не складывает валюты.

## Принятые решения

### D1. Category views и URL — принято 2026-08-01

Принято: canonical routes `/app/categories` и
`/app/categories/:categoryId`; URL directory хранит `view` и `search`, detail —
financial filters, page и `return_to`. View `all` не переносить: он создаёт
длинный смешанный список и не добавляет отдельного пользовательского outcome.
Historical `view=all` redirect нормализует к `view=active`.

### D2. Archive при активных Transaction Rules — принято 2026-08-01

Факт: текущий archive убирает категорию из active pickers, но active rule
продолжает присваивать её новым raw transactions. Это противоречивое состояние.

Принято: сервер блокирует archive, пока существуют active linked rules, и
возвращает impact с количеством и ссылкой на Rules. Правила не отключаются
скрыто. После migration Transaction Rules можно отдельно рассмотреть явный
atomic action «архивировать и отключить N правил».

### D3. Hard delete — принято 2026-08-01

Принято: сохранить удаление только для archived custom category при
нулевых ссылках во **всех** зависимостях: operations любого status,
transaction rules, raw transaction suggestions и child categories. Текущая
проверка только confirmed operations/rules недостаточна и может закончиться FK
ошибкой. API выдаёт `canDelete` и blockers; browser их не вычисляет.

### D4. Изменение `CategoryKind` — принято 2026-08-01

Принято: оставить допустимым для custom category, но показывать impact:
kind не переписывает существующие операции/суммы, зато меняет совместимость в
Import Review. Для linked category изменение kind требует явного confirmation;
system kinds остаются immutable.

### D5. Concurrency — принято 2026-08-01

Принято: использовать существующий `updated_at` как optimistic token для
update/archive/restore/delete и возвращать `409 category_*_conflict`. SSR сейчас
last-write-wins; React/API conventions Properties уже закрепили stale recovery.

## Не входит в scope

- иерархический category tree для неиспользуемого сейчас `parent_id`;
- budget/envelope taxonomy, icons/colors и пользовательская сортировка;
- массовая рекатегоризация истории;
- изменение `Operation.type`, `affects_profit` или MoneyEntry через category UI;
- объединение категорий;
- переписывание Transaction Rules или Reports внутри Categories;
- generic CRUD/schema renderer.

## Последовательность

```text
01 directory + read API
  -> 02 create
  -> 03 detail/report drill-down
  -> 04 edit
  -> 05 lifecycle/delete after D2-D5
  -> 06 replacement gate/cutover/cleanup
```

Текущее положение: Slices 01–05 completed; Slice 06 next. Каждый slice проходит
`application/API -> typed state -> UI -> tests`. Legacy
SSR остаётся operational до Slice 06, но не получает новых presentation
abstractions.

## Общий exit gate

- D1–D5 согласованы и записаны как принятые;
- canonical AppShell и cross-feature links ведут на `/app/categories*`;
- JSON API проверяет session, workspace read/write permission, CSRF и stale
  snapshot;
- summary и operation rows приходят с сервера, currencies не смешиваются;
- transfer никогда не становится доходом/расходом/profit из-за category kind;
- archive policy не оставляет необъяснимых active-rule side effects;
- delete capability учитывает все FK consumers и не удаляет историю;
- React tests покрывают directory, detail, URL state, read-only, create/edit,
  lifecycle, errors, focus и draft preservation;
- Mocha и Latte проходят на 1440/920/390 без overflow;
- historical GET routes сохраняют query и ведут в React; legacy POST отсутствуют;
- router/presenter/templates/category-only CSS/JS/SSR assertions удалены;
- каждый сохранённый consumer объяснён в delete manifest.
