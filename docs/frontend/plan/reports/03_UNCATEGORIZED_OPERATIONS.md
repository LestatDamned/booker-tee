# Slice 03: Uncategorized Operations

Статус: completed 2026-07-31.

## Outcome

Пользователь видит ограниченный список confirmed profit operations без
категории для текущих filters и может перейти к подходящему correction/detail
workflow, если такой action разрешён сервером.

## Application/repository

- Query использует workspace, date, currency, account и property filters.
- Категория определяется общей domain semantics: null или system
  `uncategorized` согласно существующей модели.
- Transfers и unconfirmed operations исключены.
- Pagination server-side, с небольшим default и жёстким maximum page size.
- Ordering deterministic: operation date descending, затем UUID.
- Count выполняется aggregate query; page не загружает ORM relationships сверх
  DTO projection.
- DTO содержит только необходимые факты: identity/version, dates, type,
  description, signed amount, currency и server capability/reason code.
- Correction URL не приходит с сервера; React строит route из operation source
  и capability только по существующему безопасному contract.

## Frontend state/UI

- Page находится в URL как `uncategorized_page`; page size фиксирован или
  bounded query parameter по существующему Workbench pattern.
- Изменение financial filters сбрасывает страницу на первую.
- `ResponsiveRecordCollection` показывает desktop table/mobile records.
- `WorkbenchPagination` отображает range/total и доступные переходы.
- Empty page после удаления последнего результата нормализуется к последней
  существующей странице без бесконечного redirect loop.
- Amount имеет sign, currency и text semantics; type не обозначается только
  цветом.
- Если correction недоступен, строка остаётся читаемой и показывает reason без
  ложной disabled action.

## Tests

Backend/API:

- default/max page size и invalid page;
- stable ordering с одинаковой датой;
- total/count/page consistency;
- no unbounded ORM operation list;
- currency/workspace/filter isolation;
- transfers/unconfirmed excluded;
- capability policy для imported/manual operations;
- query count остаётся постоянным при росте rows.

Frontend:

- first/middle/last/empty page;
- page reset after filter apply;
- Back/Forward and reload;
- row facts and correction links/capabilities;
- accessible pagination labels and focus behavior;
- mobile records без horizontal overflow.

## Exit gate

- endpoint не может вернуть неограниченное число operations;
- total и page относятся к тем же applied filters/currency, что KPI;
- deep-linked pagination стабильна;
- existing safe correction workflow переиспользуется, financial mutation не
  дублируется внутри Reports;
- desktop/tablet/mobile replacement покрыт browser tests.

## Completion record

Completed: 2026-07-31

Implemented:

- server-side page внутри существующего `GET /api/v1/reports`: default 10,
  hard maximum 25;
- отдельные count и projection queries с workspace/date/currency/account/
  property predicates, confirmed/profit-only policy и deterministic ordering;
- нормализация deep-linked empty page к последней существующей странице;
- responsive desktop table/mobile records на `ResponsiveRecordCollection`;
- URL pagination на `WorkbenchPagination` с сохранением совместимых filters;
- server capability/reason policy и переходы в существующие Manual Ledger или
  Account Ledger correction workflows;
- отдельный readonly reason вместо ложного disabled action.

Checks run:

- Ruff, ty и 38 focused Reports backend/API tests;
- полный frontend pipeline: format, lint, styles, API drift, typecheck, 270
  tests и production build;
- authenticated realistic browser audit на `1440×1000`, `920×900` и
  `390×844` без horizontal overflow, console/page/network и UX assertion
  errors.

Intentional deviations:

- page size поддерживается API как bounded parameter, но UI фиксирует его на
  компактном default 10 и не добавляет лишний control;
- imported operation ведёт в существующий Account Ledger, потому что отдельный
  correction route не существует.

Cleanup performed: placeholder Slice 03 удалён; финансовые mutations и формы
не дублировались в Reports. Legacy presentation остаётся до Slice 04.

Measurements/risks: список всегда выполняет два SQL queries (`count` и
bounded page), независимо от числа найденных rows. Reports route chunk —
`24.86 kB`, gzip `7.30 kB`; CSS — `5.14 kB`, gzip `1.18 kB`.
