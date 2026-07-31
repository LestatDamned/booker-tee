# Slice 02: Category And Property Breakdowns

Статус: planned.

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
