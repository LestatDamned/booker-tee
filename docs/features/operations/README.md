# Operations workspace

Статус: реализовано 11 августа 2026; unified reader, API, canonical React
collection, source-aware actions, cross-feature deep links и cutover завершены.

`Операции` — главный пользовательский поток всех денежных событий workspace.
Ручной ввод, подтверждённый импорт, долг и системная команда создают одну и ту же
доменную сущность `Operation`; `source` сохраняет происхождение, но не определяет,
в каком разделе пользователь должен искать запись.

## Продуктовое решение

Текущее название «Ручные операции» отражает способ создания, а не задачу
пользователя. Оно заменяется на «Операции».

```text
Операции   — что произошло с деньгами
Импорты    — как внешние данные были получены и проверены
Долги      — почему существует обязательство и как оно погашается
Активность — кто совершил значимое действие
Отчёты     — к чему привели confirmed operations
```

После подтверждения import row пользователь работает с созданной `Operation` в
общем потоке. `RawTransaction` до подтверждения остаётся только в Import Review.
Ignored, duplicate и неподтверждённые raw rows не становятся официальными
финансовыми фактами.

## Domain boundary

Persistence model не разделяется:

```text
Operation
  type: income | expense | transfer | adjustment
  source: manual | bank_pdf | debt | system
  status: draft | needs_review | confirmed | ignored | duplicate
  1 -> N MoneyEntry
```

`source` нужен для provenance, source-specific capabilities и правильного
correction workflow. Он не создаёт `ManualOperation` и `ImportedOperation` как
отдельные persistence entities.

Общий reader читает все workspace-scoped `Operation`. Mutation services остаются
разделёнными по инвариантам:

```text
OperationsReader                    — единый read model
ManualOperationService              — ручное создание и исправление
ImportedOperationCorrection         — разрешённые import corrections
DebtService                         — долг и составной платёж
System operation policy             — read-only, если нет отдельной команды
```

Не вводится универсальный `update_operation()`, обходящий source-specific
validation. React отображает server-owned capabilities и не выводит разрешения
из `source` самостоятельно.

## Information architecture

Первая версия переиспользует существующий collection workbench:

```text
/app/operations
/app/operations?operation_id=<uuid>
```

`operation_id` — canonical deep link первой версии. Он открывает или выделяет
операцию даже если она находится вне текущей страницы результатов. Это продолжает
существующий `targetOperation` contract и не требует преждевременной отдельной
detail page.

Маршрут `/app/operations/:operationId` добавляется только когда одной раскрытой
строки недостаточно: появляются самостоятельная длинная история, комментарии,
attachments или сложный correction workflow.

Старый `/app/ledger/manual` является query-preserving redirect на
`/app/operations` и не загружает отдельный list read model.

## Страница

```text
Операции                                      [Добавить операцию]
Все денежные события рабочего пространства

[Все] [Доходы] [Расходы] [Переводы]

[Поиск] [Период] [Счёт] [Категория] [Дополнительные фильтры]

12 августа
────────────────────────────────────────────────────────────
Аренда квартиры                                  −45 000 ₽
Основной счёт · Вручную
[Расход] [Недвижимость]                         [Исправить]
                                              [Ещё действия]

Пятёрочка                                        −3 420 ₽
Тинькофф · Импорт
[Расход] [Продукты]                            [Исправить]
                                              [Ещё действия]

Платёж по ипотеке                                −28 500 ₽
Основной счёт · Долг
[Расход] [Ипотека]                            [Открыть долг]
```

Главная иерархия строки:

1. дата, описание и сумма;
2. счёт или маршрут перевода и source;
3. тип, категория, объект и только исключительный status;
4. доступные действия.

Источник отображается вторичной текстовой меткой и доступен в дополнительных
фильтрах. Он не становится верхнеуровневым tab и не передаётся только цветом.

По умолчанию список показывает только `confirmed`. Отменённые, дубликаты и
review-состояния остаются доступны через явный status filter; `status=all`
показывает полную историю.

## Selected operation

Deep link фокусирует и подсвечивает существующий `WorkbenchRow`, не раскрывая
панель, которая повторяет уже видимые данные. Если запись не входит в текущую
page или выборку, backend возвращает её отдельно как `target_operation` после
повторной проверки `workspace_id`, а строка явно объясняет это исключение.

Canonical переходы к источнику находятся в server-разрешённом `ActionStack`:

- import source → document/review;
- debt source → debt detail;
- workspace activity → обратно в журнал браузерной кнопкой Back.

`ExpansionPanel` используется только для реального correction/review workflow.
Отдельная detail page появится лишь вместе с уникальным содержанием: account
entries, полноценной историей, комментариями или attachments.

Backend не возвращает React `href`. Frontend строит ссылку только для известных
route types, а target endpoint повторно проверяет workspace authorization.

## Source-aware behavior

| Source     | В общем списке | Изменение                                   | Дополнительный переход |
| ---------- | -------------- | ------------------------------------------- | ---------------------- |
| `manual`   | да             | manual edit/cancel/restore/delete policy    | —                      |
| `bank_pdf` | да             | только imported correction/undo capability | документ или review    |
| `debt`     | да             | через debt workflow                         | карточка долга         |
| `system`   | да             | read-only без отдельной server command      | по provenance          |

Create CTA всегда означает ручной ввод новой операции, но остаётся на общей
странице. После создания строка получает source `manual`.

## URL state

URL владеет:

- `operation_id`;
- search query;
- operation type;
- period;
- account/category/property;
- source как secondary filter;
- page и page size.

Изменение filters сбрасывает page. Back/Forward восстанавливают фильтр, выбранную
операцию и ожидаемую scroll position. Unsaved create/edit draft остаётся local
state и не сериализуется в URL.

## User stories

### Ручной ввод

Как пользователь, я добавляю расход на странице «Операции» и сразу вижу его в
общем денежном потоке с меткой «Вручную».

### Подтверждённый импорт

Как пользователь, я подтверждаю raw row в Import Review, после чего созданная
операция появляется в общем списке с меткой «Импорт» и ссылкой на документ.

### Переход из activity journal

Как owner/admin, я нажимаю на операцию в журнале и попадаю на
`/app/operations?operation_id=<uuid>` с открытой нужной записью. Foreign или
удалённая entity не раскрывается.

### Долговой платёж

Как пользователь, я вижу principal/interest операции в общем потоке, но изменяю
сам долг и составной платёж через Debt workflow.

### Поиск независимо от происхождения

Как пользователь, я ищу «Пятёрочка» один раз и нахожу как ручные, так и
импортированные операции. Source filter нужен только для уточнения результата.

## API read model

Canonical read endpoint:

```http
GET /api/v1/operations
    ?operation_id=<uuid>
    &search=...
    &type=income|expense|transfer|adjustment
    &source=manual|bank_pdf|debt|system
    &page=1
```

Canonical DTO операции содержит:

```text
OperationItemDto
  id, version
  type, source, status
  operation_date, description
  money / entries presentation
  account, source_account, destination_account
  category, property
  provenance: typed safe union | null
  capabilities
    can_edit
    edit_kind: manual | imported | none
    can_cancel, can_restore, can_delete
    readonly_reason
```

`provenance` не содержит raw document text, storage key, credentials или
произвольный metadata JSON. List query остаётся bounded, workspace-scoped и не
делает per-operation lookups.

## Permissions and financial safety

- list/detail всегда фильтруются по `workspace_id`;
- foreign `operation_id` возвращает privacy-safe отсутствие target;
- создание требует `can_write_financial_data`;
- capabilities вычисляет backend по role, status, source и связанным entities;
- React не разрешает действие только потому, что source равен `manual`;
- transfer по-прежнему имеет `affects_profit=false` и balanced entries;
- draft/ignored/duplicate не попадают в official balances и reports;
- read migration не меняет persisted operations или financial totals.

## Non-goals первой версии

- новый persistence subtype для каждого source;
- второй ledger;
- универсальная mutation-команда для всех sources;
- bulk edit, comments, attachments и realtime;
- полнотекстовый search engine;
- новая global state/cache library;
- отдельная detail route без доказанной сложности панели.

## Документы

- [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) — безопасная последовательность
  vertical slices и replacement gate;
- [`../../domain/DOMAIN_MODEL.md`](../../domain/DOMAIN_MODEL.md) — каноническая
  финансовая модель;
- [`../workspaces/ACTIVITY_AND_AUTHORSHIP.md`](../workspaces/ACTIVITY_AND_AUTHORSHIP.md)
  — safe entity reference из activity journal.
