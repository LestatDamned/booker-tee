# Stage 07 / Wave A: Reports

Статус: active; Slices 01–03 completed, Slice 04 next.

Этот child stage переносит authenticated Reports из Jinja/HTMX в React и
одновременно исправляет обнаруженные дефекты финансовой корректности и чтения
данных. Цель — не буквально повторить текущую реализацию, а сохранить полезный
пользовательский workflow на безопасном reporting read model.

```text
период и точные фильтры
  -> явно выбранная валюта
  -> доходы / расходы / прибыль
  -> балансы счетов на дату
  -> категории и объекты
  -> ограниченный список операций без категории
```

## Связанные документы

- [`INVENTORY.md`](INVENTORY.md) — наблюдаемое SSR-поведение, кодовые границы,
  consumers и delete manifest;
- [`NUANCES.md`](NUANCES.md) — обязательные финансовые, архитектурные, UX и
  performance-нюансы;
- [`01_REPORTING_CORE_AND_OVERVIEW.md`](01_REPORTING_CORE_AND_OVERVIEW.md) —
  currency-safe reporting core, JSON API, KPI, фильтры и балансы;
- [`02_BREAKDOWNS.md`](02_BREAKDOWNS.md) — разрезы по категориям и объектам;
- [`03_UNCATEGORIZED_OPERATIONS.md`](03_UNCATEGORIZED_OPERATIONS.md) —
  ограниченный и пагинируемый список операций без категории;
- [`04_CUTOVER_AND_CLEANUP.md`](04_CUTOVER_AND_CLEANUP.md) — canonical links,
  redirects, replacement checks и удаление legacy presentation.

## Почему это отдельный child stage

Текущий `ReportsService` одновременно обслуживает SSR Reports, Dashboard и chat
integration; его pure summary также импортирует Categories. При этом текущая
страница смешивает валюты под label валюты workspace, группирует объекты по
имени, делает N+1 balance queries, загружает все operations/documents и может
seed-ить категории внутри GET.

Следовательно, перенос требует сначала стабилизировать общий read boundary, а
не просто добавить API над существующим `build_overview()`.

Оценка сложности: средне-высокая, около `7/10`. Планирование для одного
разработчика, включая API, React, tests, browser audit и cleanup: `10–16`
focused engineering days. Это диапазон планирования, не срок и не SLA.

## Порядок slices

| Порядок | План                                                                     | Статус    | Пользовательский результат                                    | Оценка   |
| ------- | ------------------------------------------------------------------------ | --------- | ------------------------------------------------------------- | -------- |
| 1       | [`01_REPORTING_CORE_AND_OVERVIEW.md`](01_REPORTING_CORE_AND_OVERVIEW.md) | completed | Видит корректные KPI одной валюты, фильтры и балансы на дату  | 4–6 дней |
| 2       | [`02_BREAKDOWNS.md`](02_BREAKDOWNS.md)                                   | completed | Анализирует категории и объекты без слияния сущностей         | 2–3 дня  |
| 3       | [`03_UNCATEGORIZED_OPERATIONS.md`](03_UNCATEGORIZED_OPERATIONS.md)       | completed | Находит и просматривает bounded список операций без категории | 2–3 дня  |
| 4       | [`04_CUTOVER_AND_CLEANUP.md`](04_CUTOVER_AND_CLEANUP.md)                 | next      | Использует только React Reports; legacy presentation удалён   | 2–4 дня  |

## Канонические маршруты на время общей миграции

```text
/app/reports
/api/v1/reports
```

После replacement gate исторический `GET /reports` становится
query-preserving redirect на `/app/reports`. Временный `/app` prefix удаляется
только общим Stage 07 routing cutover.

## Target boundary

```text
React Reports / Dashboard / Chat
  -> ReportingOverviewReader
  -> ReportsRepository
  -> bounded workspace-scoped aggregate queries
```

`Categories` может переиспользовать узкий pure financial summary/value object,
но не browser DTO и не весь Reports overview.

Ответственность слоёв:

- API router валидирует HTTP query, auth и сериализует DTO;
- application reader нормализует filters и оркестрирует read projections;
- repository владеет SQL aggregates и workspace predicates;
- domain/pure policy исключает transfers, работает с `Decimal` и одной
  explicit currency;
- React владеет URL state, labels, sorting presentation, layout и navigation;
- сервер остаётся владельцем financial truth и filter authorization.

Не вводить generic reporting framework, CQRS infrastructure или Protocol ради
названия паттерна. Узкий repository interface появляется только там, где он
реально упрощает composition и replacement tests.

## Общий API contract

`GET /api/v1/reports` принимает:

```text
date_from
date_to
currency
account_id
category_id
property_id
uncategorized_page
uncategorized_page_size
```

Категорийная сортировка остаётся в browser URL:

```text
category_sort=name|income|expense|profit
category_sort_dir=asc|desc
```

Она управляет presentation-порядком ограниченного набора aggregate rows и не
обязана становиться financial API filter.

Response projection содержит:

- normalized applied filters, включая explicit `currency`;
- filter options для accounts, categories, properties и currencies;
- `summary` с currency и decimal-string values;
- account balances с собственной currency и фактом `asOf`;
- category/property rows с UUID, display name и money facts;
- bounded uncategorized page и total count;
- optional next review document reference/capability для empty state.

API не возвращает русские labels, CSS tones, action URLs, ORM objects или
legacy ViewModels. Money передаётся decimal strings и проверяется runtime schema
на frontend.

## Общие exit gates

Child stage завершён только когда:

- summary/category/property totals никогда не смешивают currencies;
- internal transfers не входят в income, expense, profit и property totals;
- duplicate property names не объединяются;
- все reads workspace-scoped, bounded и side-effect free;
- query count не растёт на каждый account/operation/document;
- Dashboard, Chat и Categories переведены на сохранённые узкие контракты;
- `/app/reports` покрывает URL filters, Back/Forward, reload и empty/error states;
- table sorting доступна с клавиатуры и публикует `aria-sort`;
- desktop `1440×1000`, tablet `920×900`, mobile `390×844` проходят без
  horizontal page overflow;
- canonical links ведут в React, historical GET сохраняет query string;
- legacy router, Jinja presenter/templates, HTMX partial и replacement-only
  tests удалены;
- оставшийся `.report-table` имеет именованного SSR consumer либо удалён вместе
  с последним consumer.
