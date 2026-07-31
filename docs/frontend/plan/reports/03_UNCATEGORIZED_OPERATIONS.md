# Slice 03: Uncategorized Operations

Статус: planned.

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
