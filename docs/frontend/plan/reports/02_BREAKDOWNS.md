# Slice 02: Category And Property Breakdowns

Статус: completed 2026-07-31.

## Outcome

Пользователь анализирует income, expense и profit выбранной currency по
категориям и объектам. Строки имеют стабильную entity identity, сортировка
сохраняется в URL и одинаково работает в desktop table и mobile records.

## Application/repository

- Category aggregate группирует по category UUID/system uncategorized key.
- Property aggregate группирует по property UUID, не display name.
- Оба aggregates используют те же workspace/date/currency/entity predicates,
  что KPI.
- Transfers и unconfirmed operations исключены.
- Rows имеют deterministic secondary order по UUID после normalized name.
- Archived references, присутствующие в истории, не теряют identity и получают
  `isActive` fact.

Если overview endpoint уже возвращает эти rows в Slice 01, Slice 02 завершает
их production tests и UI. Не добавлять второй endpoint без измеренной причины
размера/latency.

## Frontend state/UI

- Category sort values: `name`, `income`, `expense`, `profit`.
- Default: `name asc`; numeric default: `desc`.
- Sort и direction находятся в URL и сохраняются period navigation.
- Header control публикует `aria-sort`; сортировка не зависит от HTMX.
- Category row может вести в ещё живой canonical Categories route, сохраняя
  совместимый period context.
- Property link добавляется только если detail route существует и ownership
  semantics ясны; иначе row остаётся честным read-only fact.
- `ResponsiveRecordCollection` переключает table/mobile representation.
- Каждая сумма показывает applied currency через `MoneyValue` или явный
  section-level currency context, понятный screen reader.
- Empty breakdown внутри непустого report объясняет отсутствие связей, а не
  изображает общий empty report.

## Tests

Backend:

- duplicate category/property names дают отдельные UUID rows;
- uncategorized category semantics;
- archived category/property historical row;
- filters и currency одинаковы для KPI и breakdowns;
- transfer excluded;
- deterministic ordering;
- workspace isolation;
- aggregate query count не зависит от operation count.

Frontend:

- all sort fields and direction toggles;
- numeric default descending;
- `aria-sort` и keyboard activation;
- sort URL survives reload/Back/Forward/month navigation;
- duplicate names render as distinct rows;
- empty category/property states;
- responsive table/record parity without horizontal page overflow.

## Exit gate

- property grouping bug исправлен по UUID;
- category/property totals совпадают с summary filters и currency;
- HTMX partial больше не является необходимым replacement contract;
- sorting доступна, deep-linkable и не требует server-rendered HTML;
- desktop/tablet/mobile представляют одинаковые financial facts.

## Completion record

Completed: 2026-07-31

Implemented:

- category и property breakdowns на существующем overview endpoint;
- distinct UUID identity для одинаковых category/property names и отдельная
  system identity для `Без категории`;
- URL-сортировка categories по name/income/expense/profit без преобразования
  decimal strings в `float`;
- desktop `aria-sort` headers и mobile sorting controls;
- category detail links с сохранением совместимого периода;
- отдельные empty states для categories и properties.

Checks run:

- Ruff, ty и 28 focused Reports backend/API tests;
- полный frontend pipeline: format, lint, styles, API drift, typecheck, 264
  tests и production build;
- authenticated realistic browser audit на `1440×1000`, `920×900` и
  `390×844` без horizontal overflow, console/page/network и UX assertion
  errors.

Intentional deviations:

- новый endpoint не добавлялся: Slice 01 overview уже возвращает bounded
  aggregate rows;
- property rows остаются read-only, потому что canonical React detail route
  ещё отсутствует.

Cleanup performed: placeholder Slice 02 удалён; legacy Reports сохраняется до
Slice 04 replacement gate.

Measurements/risks: Reports route chunk — `19.71 kB`, gzip `6.02 kB`; CSS —
`4.09 kB`, gzip `1.00 kB`. Следующий рост response/UI относится только к
bounded uncategorized page Slice 03.
