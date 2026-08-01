# Stage 07 / Wave A: Reports

Статус: completed 2026-07-31; cutover и post-cutover period report завершены.

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

- [`PERIOD_REPORT_DESIGN_GUIDELINES.md`](PERIOD_REPORT_DESIGN_GUIDELINES.md) —
  актуальный единый design contract следующей итерации Reports, источники best
  practices, композиция, визуализация и acceptance gates;
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
| 4       | [`04_CUTOVER_AND_CLEANUP.md`](04_CUTOVER_AND_CLEANUP.md)                 | completed | Использует только React Reports; legacy presentation удалён   | 2–4 дня  |

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

Текущее presentation state остаётся в browser URL:

```text
breakdown=properties              # categories по умолчанию
metric=income|profit              # expense по умолчанию
```

Оно управляет выбранным ranked list и не становится financial API filter.
Исторические `category_sort*` query не являются частью актуального UI.

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
- breakdown и metric доступны с клавиатуры, отражены в URL и имеют явное
  selected state;
- desktop `1440×1000`, tablet `920×900`, mobile `390×844` проходят без
  horizontal page overflow;
- canonical links ведут в React, historical GET сохраняет query string;
- legacy router, Jinja presenter/templates, HTMX partial и replacement-only
  tests удалены;
- оставшийся `.report-table` имеет именованного SSR consumer либо удалён вместе
  с последним consumer.

## Post-cutover UX consolidation — 2026-07-31

После пользовательского аудита canonical Reports presentation упрощён без
изменения financial read model:

- chart и дублирующая exact table заменены одним ranked list с видимыми точными
  суммами и пропорциональными bars;
- Categories и Properties представлены взаимоисключающими tabs, поэтому
  secondary/empty content не увеличивает основную страницу;
- bounded uncategorized projection сохранён в API, но overview показывает
  только компактный actionable notice;
- account balances остаются в API contract для совместимости read model, но
  canonical balance UI принадлежит Accounts;
- default view показывает expenses by category; breakdown и metric сохраняются
  в URL.

Эта consolidation была промежуточной итерацией. После расширенного
пользовательского аудита принято следующее направление: единый итог периода,
обязательные opening/closing balances по счетам и одновременно видимые income
и expense breakdowns. Актуальный контракт и обоснование находятся в
[`PERIOD_REPORT_DESIGN_GUIDELINES.md`](PERIOD_REPORT_DESIGN_GUIDELINES.md).

Детальные Slice 01–04 документы выше и этот раздел остаются completion record
исходного cutover и промежуточной итерации. Они не являются основанием
возвращать superseded presentation или удалённый SSR.

## Period report implementation — 2026-07-31

Итерация из `PERIOD_REPORT_DESIGN_GUIDELINES.md` реализована пятью этапами:

1. opening/closing/change account projection и общий balance summary;
2. единая верхняя финансовая картина периода;
3. одновременно видимые income/expense ranked breakdowns без скрытых строк;
4. account/category drill-down с сохранением report context;
5. reconciliation, zero/negative/inactive/long-list fixtures, keyboard focus и
   reflow audit на `320px`.

Финальный browser audit пройден на `1440×1000`, `920×900`, `390×844`; mobile
сценарий дополнительно проверяет reflow на `320px` без horizontal overflow.

## UX evolution — started 2026-08-01

Повторный аудит выявил следующий presentation gap: двунаправленная категория
распадается между income/expense lists и не показывает свой итог. Принято
направление unified category cash-flow matrix с общей bilateral scale и exact
income/expense/result values. Параллельно Reports переводится с fixed centered
container на всю доступную ширину workspace.

Решение, источники, rejected alternatives и этапы зафиксированы в разделах
15–17 [`PERIOD_REPORT_DESIGN_GUIDELINES.md`](PERIOD_REPORT_DESIGN_GUIDELINES.md).

Этап 1 завершён 2026-08-01: Reports использует всю content-box ширину workspace;
automated browser gate дополнительно проверяет `1920×1080` и `2560×1440`.

Этап 2 завершён 2026-08-01: верхняя финансовая картина уплотнена в одну
адаптивную summary rail, а детализация по счетам использует всю ширину под ней.
Нулевые потоки получили нейтральную money semantics без положительного знака.

Этап 3 завершён 2026-08-01: отдельные income/expense lists заменены единой
responsive category cash-flow matrix. Каждая категория показывает поступления,
расходы и итог вместе; bilateral bars используют общий absolute scale.

Этап 4 завершён 2026-08-01: matrix получила URL-backed сортировку по обороту,
поступлениям, расходам и итогу. Unified category drill-down открывает обе
стороны потока и сохраняет полный report context для возврата.

Этап 5 завершён 2026-08-01: после общей summary rail category matrix занимает
primary-область, а счета — supporting pane. На широком desktop они стоят рядом;
на tablet/mobile категории идут раньше счетов. Представление счетов адаптируется
к ширине своего контейнера и не создаёт тесную четырёхколоночную таблицу.

Этап 6 завершён 2026-08-01: header и сортировка category matrix объединены,
строки и bars уплотнены, а четыре mobile tabs заменены одним доступным select.
Все категории и точные суммы по-прежнему видимы без раскрытия.

Этап 7 завершён 2026-08-01: accounts supporting pane переведён на compact
records при любой ширине, поэтому длинные суммы больше не обрезаются.
Аналитическая пара ограничена полезной шириной `96rem` и использует пропорцию
`3/2`; category matrix больше не растягивается на весь ultrawide экран.

Этап 8 завершён 2026-08-01: category bars и общий visual scale удалены в пользу
простой sortable money table. Поступления, расходы и итог остаются точными
числами; mobile использует compact records с тем же набором данных.

Этап 9 завершён 2026-08-01: category table уплотнена по data-table практикам
Apple, Material, Carbon и Fluent. Валюта показана один раз, numeric headers
дают прямую URL-backed сортировку, общий native select сохраняет turnover sort,
а authoritative totals завершают таблицу. Все интерактивные области остаются
не меньше `44px` и доступны с клавиатуры.

Этап 10 завершён 2026-08-01: служебные «Все суммы в RUB / Сначала» удалены.
Каждый видимый column header переключает ascending/descending URL-backed sort.
Аналитическая пара снова использует всю workspace width и равные колонки, а
каждая account record явно показывает `На начало / На конец / Изменение` и
отдельное действие перехода к операциям без подчёркнутого названия-ссылки.

Этап 11 завершён 2026-08-01: read-only browser stress fixture проверяет
`24` категории и `8` счетов, двунаправленные и нулевые потоки, отрицательные и
миллиардные значения, длинные названия, обе темы и диапазон от `320px` до
`2560px`. Аудит выявил наложение длинных сумм в паре `1/1` на обычном desktop.
Теперь до `90rem` категории и счета занимают полную ширину последовательно, а
на более широком экране сохраняют равное соседнее размещение. Строки и точные
суммы нигде не скрываются и не требуют горизонтального scroll.
