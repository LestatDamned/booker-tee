# Stage 06: child plans для Import Review

Статус: active; Slice 01–02 completed, следующий — Slice 03.

Этот каталог делит complexity checkpoint Stage 06 на пользовательские
вертикальные slice. Каждый implementation slice проходит через application
read/command boundaries, versioned JSON API, React state/UI и тесты. Файлы не
являются разделением задач на backend и frontend.

## Baseline и boundary

- [`INVENTORY.md`](INVENTORY.md) — текущее поведение, consumers, ошибочно
  размещенные правила и минимальный подготовительный application refactor.
- Существующие route `/imports/documents/{document_id}/review`, Presenter,
  templates и HTMX responses продолжают работать во время реализации slice.
- Новые JSON-контракты строятся из типизированных application DTO, а не из
  legacy-объектов `Review*VM` или отрендеренного HTML.
- Подготовительная работа не включает широкий рефакторинг parsers, mapping,
  document management, repositories или ledger posting.

## Порядок child plans

| Порядок | План                                                                               | Статус  | Пользовательский результат                                              |
| ------- | ---------------------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------- |
| 1       | [`01_QUEUE_AND_READ_MODEL.md`](01_QUEUE_AND_READ_MODEL.md)                         | completed | Видит typed queue, raw/normalized rows и точный progress                 |
| 2       | [`02_VALIDATION_AND_CONTROL_TOTALS.md`](02_VALIDATION_AND_CONTROL_TOTALS.md)       | completed | Понимает validation источника и проблемы control totals                 |
| 3       | [`03_CLASSIFICATION_CATEGORY_PROPERTY.md`](03_CLASSIFICATION_CATEGORY_PROPERTY.md) | planned | Безопасно разбирает classification, category и property                 |
| 4       | [`04_TRANSFER_AND_MATCHING.md`](04_TRANSFER_AND_MATCHING.md)                       | planned | Создает или связывает transfer и видит обновление всех затронутых строк |
| 5       | [`05_DUPLICATE_AND_LIFECYCLE.md`](05_DUPLICATE_AND_LIFECYCLE.md)                   | planned | Разбирает duplicates и lifecycle строки через явные transitions         |
| 6       | [`06_CONFIRM_POST_AND_CONSISTENCY.md`](06_CONFIRM_POST_AND_CONSISTENCY.md)         | planned | Подтверждает/posting ровно один раз и получает согласованное обновление |
| 7       | [`07_CUTOVER_AND_CLEANUP.md`](07_CUTOVER_AND_CLEANUP.md)                           | planned | Завершает реальный review в React и удаляет legacy только после parity  |

Текущий следующий шаг: Slice 03 — classification/category/property command
boundary и локальный draft активной строки. Legacy review остается production
путем для mutations и полного завершения workflow.

## Ограничения последовательности

1. Slice 01 устанавливает стабильную идентичность и порядок строк, queue
   semantics и generated TypeScript contract до появления mutation UI.
2. Ошибочно размещенные server rules переносятся только тогда, когда они нужны
   первому consumer. Classification и confirmability при этом не копируются в
   TypeScript.
3. Mutation slices возвращают smallest truthful consistency set: текущую строку
   и измененные sibling rows, queue summary, document lifecycle и validation
   summary, если что-то из этого изменилось.
4. Server-state cache dependency этим планом не одобрена. Сначала проверяются
   route data и feature-local reconciliation; для новой библиотеки нужен ADR с
   конкретной обнаруженной проблемой.
5. Ни один slice не удаляет и не перенаправляет legacy review route. Это
   происходит только в Slice 07 после replacement tests и observation gate.

## Текущие ответы на архитектурные вопросы

- Для старта достаточно React Router loader data и feature-local state.
- Draft принадлежит активной строке/panel feature; server entities и financial
  truth не становятся draft state.
- `ready_to_confirm` остается вычисляемым presentation/read-model state, а
  capability и blocking reasons, на которых оно основано, принадлежат server.
- API отдает domain/application facts и capabilities, а не расположение
  компонентов, action URLs, badges, tones или русские labels.
- Optimistic confirm/post запрещен. Открытие панели и подсветка выбора могут быть
  optimistic, потому что это только UI-state.
