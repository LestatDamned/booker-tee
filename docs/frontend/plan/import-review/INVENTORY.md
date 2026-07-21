# Inventory поведения Import Review и аудит boundary

Статус: исторический baseline Stage 06 от 2026-07-21; описанный legacy runtime
удалён после replacement gate 2026-07-22.

## Проверенный scope

Основной runtime:

- `application/review/page_data.py`, `actions.py`, `status.py`,
  `validation_refresh.py`;
- `presentation/review/state.py`, `item.py`, `page.py`, `actions.py`,
  `panels.py`, `references.py`;
- `routes/review.py`, `routes/review_responses.py`;
- import models/repositories, ledger posting для raw transactions и относящиеся
  к ним import, ledger, template и presentation tests.

Inventory намеренно ограничен import review и его прямыми зависимостями:
posting, validation и references. Он не предлагает redesign всего `imports`.

## Текущий request и mutation flow

```text
GET legacy review
  -> ImportReviewPageDataLoader загружает ORM document и reference objects
  -> route может отметить document как imported и сделать commit внутри GET
  -> legacy Presenter вычисляет queue, classification, confirmability и actions
  -> Jinja рендерит страницу

POST legacy row action
  -> form parser создает command с discriminator в виде строки
  -> RawTransactionReviewUseCase владеет commit/rollback
  -> status change ИЛИ ledger posting/transfer/rule application
  -> обновляются validation и document lifecycle
  -> response renderer заново загружает весь document/page data
  -> HTMX заменяет текущую строку и выбранные OOB sibling rows
```

Транзакционная command-обертка и workspace-scoped repository lookups — хорошая
основа. JSON API должен вызывать application use cases напрямую и не должен
переиспользовать HTMX response renderer.

## Наблюдаемое продуктовое поведение

### Загрузка, идентичность и источник

- Review ограничен одним document и упорядочен по постоянному
  `RawTransaction.row_index`.
- Стабильные identity уже существуют: UUID document, raw row и parse attempt.
- Account документа используется как fallback, если у строки нет своего account.
- Raw payload и исходные date/description/amount/currency/balance сохраняются;
  рядом по возможности показываются normalized values.
- Latest parse attempt определяется порядком relationship (`created_at desc`) и
  владеет control totals и сохраненным validation report.
- Доступ workspace-scoped, legacy route требует import-management permission.
  React API должен отдельно передавать read capability и financial-write
  capability.

### Queue и lifecycle

- Queue progress считается как `done / total`; первая оставшаяся строка задает
  переход «к следующей».
- Тексты и workflow для empty, in-progress и complete queue относятся к
  presentation.
- Confirm, transfer link, ignore и duplicate могут обновить validation и
  перевести document в `imported`.
- Undo posting восстанавливает reviewable status строки и обновляет затронутые
  данные.
- Rule application может изменить suggestions нескольких sibling rows.
- Создание category обновляет options всех non-final rows в текущей HTMX
  реализации.

### Classification и confirmability

- Приоритет classification: explicit value, значение из rule suggestion,
  inference по знаку amount (`income`/`expense`), иначе unknown.
- Сейчас строка показывается confirmable, только если она non-final, достаточно
  нормализована для posting, имеет effective source account и поддерживаемую
  classification, а income/expense имеет настоящую category. Для transfer нужны
  два разных account.
- `ready_to_confirm` вычисляется и должно оставаться вне database enum.
- Данные rule suggestion частично выводятся из status/foreign key, частично
  читаются из `raw_payload["rule_suggestion"]`.

### Validation и consistency

- Status/posting changes пересчитывают totals и balance-chain validation по всем
  строкам и сохраняют report в latest parse attempt.
- Ignored amounts учитываются отдельно как объясненные исключения; duplicate и
  failed rows исключаются; possible duplicates требуют review.
- Transfer matching может изменить строку другого document, поэтому truthful
  consistency boundary не всегда ограничивается текущей строкой/document.
- Корректность HTMX сейчас основана на полной перезагрузке и явных OOB row IDs.
  React нужны те же факты в typed mutation result, а не HTML fragments.

## Правила, находящиеся в неправильном слое

### Нужно перенести до появления JSON consumer

1. **Queue completion semantics** — `presentation/review/state.py` и `page.py`
   определяют terminal statuses и первую оставшуюся строку. Эти факты общие для
   API, document lifecycle и mutations, поэтому ими должны владеть pure domain
   policy и typed application queue projection.
2. **Classification** — `ReviewClassificationResolver` выводит смысл операции в
   presentation. Pure precedence rule нужно перенести в domain/application и
   возвращать typed `operation_type` вместе с `source`; presentation только
   добавляет labels.
3. **Confirmability** — `ReviewConfirmabilityPolicy` защищает financial action,
   но существует только в presentation. Capability evaluation и стабильные
   reason codes должны перейти в server boundary. React и legacy могут
   переводить codes в пользовательский текст.
4. **Lifecycle transitions** — `status.py` преобразует произвольные строки в
   statuses, но не проверяет transition из текущего state. Фактической защитой
   служит видимость UI-action. Application/domain должны отклонять forged или
   stale transitions до появления JSON mutations.
5. **Rule suggestion state** — активность/auto-application suggestion является
   application/domain fact, а не результатом разбора JSON payload Presenter'ом.

### Оставить в presentation/frontend

- `ready_to_confirm` как display state, вычисленный из server capability;
- labels, tones, badges, warning copy и форматирование money/date;
- open/closed state panel, active panel, focus и local draft;
- расположение actions, icons, confirm-dialog copy и navigation URLs;
- тексты empty state и workflow steps.

### Уже размещено правильно

- statement totals и balance-chain calculations в import domain;
- orchestration обновления validation в application;
- atomic posting, dedupe checks, правила баланса/account для transfer и
  workspace reference resolution в ledger application/domain;
- query/update mechanics в repositories;
- transaction commit/rollback во внешнем review use case.

## Конкретные противоречия, которые нельзя копировать

1. `MATCHED` является terminal в legacy Presenter `FINAL_RAW_STATUSES`, но
   остается reviewable в `ImportQueryRepository`, postable в ledger domain,
   refreshable в HTMX responses и не завершает `ImportedDocumentStatusUpdater`.
   `mark_unique` также записывает `MATCHED`. Согласованный текущий смысл:
   «possible duplicate признан уникальным и все еще требует обработки», а не
   queue done. Slice 01 должен закрепить этот смысл тестом до публикации counts.
2. Presenter confirmability требует настоящую category для income/expense, но
   прямой posting может использовать fallback uncategorized. Crafted request
   может обойти видимое safety rule. Command boundary должен обеспечивать
   выбранную safety policy до реализации confirm API.
3. Presentation проверяет `row.operation_type`, но persisted raw-transaction
   model содержит только `suggested_operation_type`; explicit branch для
   настоящих ORM rows сейчас мертв. Новый typed classification input должен
   содержать только поддерживаемые данные или явное application draft value.
4. Legacy GET может изменить document lifecycle и выполнить commit. React read
   endpoint обязан быть side-effect free. Lifecycle repair выполняется после
   commands или отдельной application operation, но не loader'ом.
5. `RawTransactionReviewCommand` принимает широкий набор optional fields для
   любого action. Несогласованные combinations чаще всего игнорируются. Mutation
   slices должны постепенно вводить action-specific commands/API schemas.
6. Transfer request запрещает два одновременных match target, но другие
   action/status transitions полагаются на UI visibility вместо server policy.
7. Legacy errors — строки/HTML со статусом `400`. React нужны стабильные `404`,
   `409` и `422` envelopes с сохранением draft и stale context.

## Минимальный подготовительный application refactor

Создать параллельный read boundary, не переделывая сначала legacy Presenter:

```text
imports/domain/review_queue.py
  -> единая terminal/reviewable policy и входы для queue projection

imports/application/review/read_model.py
  -> frozen typed DTO для document, ordered row identity/source summary,
     queue progress и capabilities
  -> ImportReviewReader.read(workspace_id, document_id, can_write)

api/v1/import_review/
  -> Pydantic response schemas и mapper из application DTO
```

Ограничения:

- DTO используют concrete types, а не `object`, ORM instances или legacy VM.
- Initial reader может переиспользовать существующие workspace-scoped repository
  queries, но не вызывает Presenter code и не изменяет document status.
- `ImportReviewPageDataLoader` сохраняется для legacy до следующих slices; не
  превращать его в universal facade.
- Для Slice 01 переносится только terminal/queue policy. Classification,
  confirmability и transition policies переносятся в slice первого использования.
- Не вводить repository Protocol только ради стиля. Узкий read interface нужен,
  только если boundary доказан тестами или вторым adapter.
- Для первого slice не требуется database migration.

## Контракт первого vertical slice

Первый response содержит application facts, а не component layout:

- identity document, filename, persisted status и source account reference;
- queue `total`, `completed`, `remaining`, `first_remaining_item_id` и ordered
  stable item IDs;
- UUID, row index, persisted status, terminal/reviewable flags, raw source summary
  и normalized date/description/money каждой queue item, если они доступны;
- page capability `can_write` и стабильный readonly reason/code;
- пока без action URLs, panel templates, icon names, tones, переведенных status
  labels и утверждения `ready_to_confirm`.

API и frontend tests должны доказать workspace isolation, deterministic ordering,
reviewable-семантику `MATCHED`, empty/partial/complete queues, сохранность raw
source, readonly rendering и отсутствие зависимости от legacy HTML/ViewModel.

## Явные non-goals подготовки

- рефакторинг всех imports services/repositories;
- изменение parser или mapping pipelines;
- изменение database enums или persistence для `ready_to_confirm`;
- замена ledger posting или transfer suggestion algorithms;
- добавление cache/global state/form libraries;
- удаление или redirect legacy import review.
