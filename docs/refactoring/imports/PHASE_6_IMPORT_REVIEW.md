# Phase 6 — Extract Import Review

Статус: подробный план, готовый к поэтапному обсуждению и реализации.

Этот документ раскрывает Phase 6 из
[`ROADMAP.md`](ROADMAP.md). Он фиксирует границы feature, порядок маленьких
изменений, транзакционную модель и проверки. Цель — не просто переместить
файлы, а сделать `import_review` единственным владельцем пользовательской
проверки импортированных строк.

## Результат этапа простыми словами

До этапа:

```text
React -> новый review workflow -> ledger -> imports
chat  -> legacy review workflow -> ledger -> imports
```

После этапа:

```text
React -> import_review
chat  -> import_review

import_review
  -> читает и изменяет review-состояние в imports
  -> просит ledger провести готовые финансовые данные
  -> применяет transaction rules
  -> атомарно связывает результат с RawTransaction

ledger
  -> создаёт Operation и MoneyEntry
  -> не управляет import document и review lifecycle
```

Пользовательские маршруты, API schemas и финансовое поведение при этом не
меняются.

## Почему недостаточно перенести папку

На старте этапа `imports/application/review` уже выглядел как отдельная feature,
но граница была неполной. После переноса основной остаток выглядит так:

1. React API использует новые typed services:
   `ImportReviewConfirmationService`, `ImportReviewLifecycleService`,
   `ImportReviewTransferService`.
2. Chat confirmation, transfer и lifecycle используют общие actors, а создание
   и применение нового правила — общий `ImportReviewRuleCreator`.
3. API `apply-rules` намеренно остаётся отдельным сценарием: он только повторно
   применяет существующие правила и не создаёт новое.
4. `RawTransactionPoster` расположен в `ledger`, но сам загружает и связывает
   `RawTransaction`, пересчитывает document validation и меняет document
   status.
5. API review services делают `commit` внутри себя, тогда как chat должен
   сохранить financial mutation и consume action token одним commit.

Поэтому механический move дал бы новое имя пути, но сохранил бы две реализации
и обратную зависимость `ledger -> imports review`.

## Зафиксированная граница ответственности

### Остаётся в `imports`

- `UploadedDocument`, `ParseAttempt`, `RawTransaction`;
- storage, extraction и parser registry;
- known/unknown statement processing;
- statement mapping;
- нормализация;
- statement validation и control totals;
- обнаружение exact/possible duplicates;
- persisted statuses `UploadedDocumentStatus` и `RawTransactionStatus`;
- хранение raw source и parse artifacts.

`imports` отвечает на вопрос: «Что удалось извлечь из документа и в каком
состоянии находятся исходные строки?»

### Переезжает в `import_review`

- очередь пользовательской проверки;
- классификация строки как income/expense/transfer;
- confirmability и blocking reason codes;
- допустимые lifecycle actions;
- duplicate evidence для пользователя;
- read model экрана review;
- подтверждение income/expense;
- создание, сопоставление и связывание transfer;
- user-triggered применение transaction rules;
- undo posting;
- координация обновления review/document после financial mutation.

`import_review` отвечает на вопрос: «Какое решение пользователь может принять
по строке и как атомарно применить это решение?»

### Остаётся в `ledger`

- создание `Operation`;
- создание `MoneyEntry`;
- финансовые инварианты income/expense/transfer;
- balance и currency checks;
- ledger idempotency и confirmed-operation constraints;
- изменение уже подтверждённых ledger records по ledger-specific workflows.

`ledger` отвечает на вопрос: «Как корректно записать готовый финансовый факт?»

### Остаётся в `transaction_rules`

- хранение правил;
- matching;
- построение suggestions;
- применение rule policy к reviewable rows.

`import_review` только решает, когда пользовательское действие должно создать
или применить правило.

## Особые решения по спорным файлам

| Текущий файл | Решение | Причина |
| --- | --- | --- |
| `domain/review_classification.py` | Перенести | Часть пользовательского решения |
| `domain/review_confirmability.py` | Перенести | Определяет возможность review action |
| `domain/review_lifecycle.py` | Перенести | Определяет допустимые действия пользователя |
| `domain/review_queue.py` | Перенести | Очередь существует только для review workflow |
| `domain/review_messages.py` | Оставить в `imports` | Сейчас используется statement deduplication pipeline |
| `application/review/validation_read_model.py` | Перенести | Это review projection |
| `application/review/validation_calculation.py` | Оставить в `imports` | Проверяет целостность выписки, а не UI workflow |
| `application/review/validation_refresh.py` | Оставить в `imports` | Обновляет persisted validation документа |
| `application/review/actions.py` | Удалён в transfer slice 6.3b | Legacy dispatcher больше не имеет consumers |
| `application/review/status.py` | Удалён в lifecycle slice 6.3b | Chat использует общий lifecycle actor |
| `ledger/application/transfer_suggestions.py` | Перенести алгоритм в `import_review` | Сопоставляет import row с review-вариантами |
| `ledger/application/raw_transaction_posting.py` | Разделить в 6.6 | Сейчас смешивает review orchestration и ledger posting |
| `ledger/application/imported_operations.py` | Оставить ledger correction; вынести import undo | В файле находятся две разные ответственности |

`review_messages.py` повторно оценивается в Phase 8, когда duplicate warning
перестаёт храниться как normalization error.

## Минимальная целевая структура

Структура развивается только по существующим ответственностям. Пустые
симметричные папки и generic abstractions не создаются.

```text
src/app/features/import_review/
  errors.py
  repository.py                 # только если review queries/writes реально выделены

  domain/
    classification.py
    confirmability.py
    lifecycle.py
    queue.py

  application/
    classification.py
    reading.py
    duplicate_evidence.py
    transfer_options.py
    confirmation.py
    lifecycle.py
    transfers.py
    rules.py
    undo.py
```

Это ориентир, а не требование создать все файлы заранее. Существующие cohesive
файлы перемещаются как есть. Два небольших файла объединяются только когда у
них один владелец и одно направление изменения.

## Транзакционная модель

### Правило

Самый внешний application workflow владеет `commit` и `rollback`.

Для HTTP таким workflow является import-review application service. Для chat —
chat use case, потому что он должен атомарно сохранить две части:

```text
consume chat action token
+
import-review financial mutation
+
review/document state update
=
one database commit
```

### Общий actor

Общая mutation-логика React и chat выполняется transaction-neutral actor:

```text
ImportReviewConfirmationActor.apply(...)
ImportReviewLifecycleActor.apply(...)
ImportReviewTransferActor.apply(...)
```

Actor:

- принимает typed command;
- выполняет проверки и mutations;
- может делать `flush`;
- не делает `commit`;
- не делает `rollback`;
- не знает про HTTP или chat state.

Внешний workflow:

```text
API service
  -> actor.apply(...)
  -> commit

Chat use case
  -> claim action token
  -> actor.apply(...)
  -> commit
```

Не использовать:

- параметр `commit: bool`;
- commit внутри repository;
- commit в FastAPI router;
- generic `Manager`, `Processor` или универсальный UnitOfWork ради одного
  сценария;
- event bus для синхронной financial mutation.

Transaction-neutral actor добавляется только там, где один и тот же mutation
действительно вызывают API и chat. Он живёт в том же модуле, что и внешний
service, чтобы не умножать файлы.

## Последовательность реализации

Каждый commit должен оставлять приложение запускаемым и тесты соответствующей
области зелёными. Behavioral fix, file move и массовое переименование не
объединяются без необходимости.

### Commit 6.1 — Move pure review domain

Статус: completed 2026-07-28.

Выполнено без изменения policy behavior:

- создан минимальный package `src/app/features/import_review/domain`;
- перемещены classification, confirmability, lifecycle и queue;
- production, API schemas и tests переведены на defining modules;
- compatibility imports и package-level re-exports не создавались;
- `RawTransactionStatus`, `review_messages` и statement validation сохранены
  в `imports`.

#### Проблема

Чистые review policies лежат внутри `imports/domain`, хотя statement processing
ими не владеет.

#### Изменения

Переместить без изменения логики:

```text
imports/domain/review_classification.py
  -> import_review/domain/classification.py

imports/domain/review_confirmability.py
  -> import_review/domain/confirmability.py

imports/domain/review_lifecycle.py
  -> import_review/domain/lifecycle.py

imports/domain/review_queue.py
  -> import_review/domain/queue.py
```

Обновить явные imports в production и tests.

Не создавать compatibility re-exports, если repository-wide search
подтверждает, что все consumers меняются в одном commit. Не наполнять
`__init__.py` facade imports.

#### Не меняется

- enums persisted statuses остаются в `imports/domain/types.py`;
- `OperationType` остаётся в `ledger/domain/types.py`;
- правила и reason codes не меняются;
- API JSON values не меняются;
- тестовые файлы пока физически не переносятся — это Phase 7.

#### Проверки

- pure classification tests;
- confirmability matrix;
- lifecycle transition matrix;
- queue ordering/progress tests;
- Ruff и ty.

#### Exit

В `imports/domain` больше нет review-specific policies. Новый domain не
импортирует FastAPI, SQLAlchemy session, repository или ORM models.

### Commit 6.2 — Move review read side

Статус: completed 2026-07-28.

Выполнено без изменения read behavior:

- review classification/application DTO и reference workflows перемещены в
  `import_review/application/classification.py`;
- read model, duplicate evidence, transfer options и validation projection
  перемещены в `import_review/application`;
- transfer suggestion matching перемещён из `ledger/application` в
  `import_review/application`;
- API, chat и tests используют defining modules без compatibility re-exports;
- calculation, storage и refresh document validation объединены в
  `imports/application/pipelines/document_validation.py`;
- три validation-файла заменены одним, поэтому общее количество Python-файлов
  не выросло.

#### Проблема

Read model уже предназначен только для Import Review, но лежит в `imports` и
получает transfer suggestions из ledger application.

#### Изменения

Перенести:

- classification/reference DTO и draft evaluation;
- `ImportReviewReader`;
- review DTO;
- duplicate evidence reader;
- transfer options reader;
- validation review projection.

Перенести алгоритм transfer suggestions из
`ledger/application/transfer_suggestions.py` в `import_review`. Ledger
repository может остаться источником manual transfer candidates, но review
решает, как сопоставить их с raw rows и как представить пользователю.

`ImportReviewReader` продолжает зависеть от узких `Protocol`, а concrete
repositories/services собираются в API composition root.

Расчёт document validation остаётся в `imports`. При удалении старой
`imports/application/review` функции `calculate_document_validation()` и
`refresh_document_validation()` переносятся в существующий imports-owned
validation pipeline. Если их можно объединить с
`pipelines/validation_result.py` без ухудшения cohesion, три маленьких файла
сводятся к одному imports-owned модулю.

#### Не меняется

- API schemas и paths;
- порядок review rows;
- capabilities;
- duplicate matching semantics;
- transfer matching window;
- SQL до отдельного подтверждённого repository split.

#### Проверки

- import review read-model tests;
- duplicate evidence tests;
- transfer suggestion/read tests;
- document validation projection tests;
- read API tests;
- query-count regression, если текущий test существует.

#### Exit

Review read model собирается внутри `import_review`. `ledger/application` больше
не владеет review transfer-suggestion algorithm.

### Commit 6.3 — Move mutation actors

Статус: 6.3a, confirmation, transfer и lifecycle slices 6.3b completed
2026-07-28.

#### Проблема

Confirmation, lifecycle, transfer, rules и undo находятся под `imports`, прямо
создают concrete repositories/services и имеют разные transaction contracts.

#### Изменения

В 6.3a существующие mutation services без изменения поведения перенесены в
`import_review/application`: `confirmation.py`, `lifecycle.py`,
`transfers.py`, `rules.py` и `undo.py`. React API и профильные тесты сразу
переключены на defining modules; compatibility re-exports не создавались.
Текущие `commit`/`rollback` сохранены, чтобы не смешивать file move с изменением
транзакционного поведения.

В 6.3b:

- выделить transaction-neutral actors внутри перенесённых модулей для общих
  React/chat workflows;
- сохранить replay после `IntegrityError`;
- охарактеризовать внешнее владение `commit`/`rollback`;
- не выделять actor для сценария с одним потребителем только ради симметрии.

Вертикальный confirmation slice 6.3b завершён:

- `ImportReviewConfirmationActor.apply()` содержит общие проверки и mutations,
  но не делает `commit`/`rollback`;
- API `ImportReviewConfirmationService` владеет commit, rollback и replay после
  `IntegrityError`;
- chat сначала атомарно claim-ит action state, вызывает тот же actor и делает
  один общий commit;
- `ChatConversationState.id` используется как posting idempotency key, а
  актуальный `ChatReviewQueueItem.status` — как `expected_status`;
- legacy confirmation branch удалена из `RawTransactionReviewer`;
- новый файл, generic Unit of Work и repository abstraction не создавались.

Вертикальный transfer slice 6.3b завершён:

- `ImportReviewTransferActor.apply()` обслуживает создание перевода,
  сопоставление двух raw rows и связь с существующим ручным переводом без
  `commit`/`rollback`;
- API `ImportReviewTransferService` владеет commit, rollback и replay после
  `IntegrityError`;
- chat builder создаёт те же typed transfer commands и передаёт
  `ChatConversationState.id` как idempotency key;
- chat claim и transfer mutation фиксируются одним commit;
- неиспользуемые `RawTransactionReviewer`, legacy command/result и весь
  `application/review/actions.py` удалены;
- `expected_status`, новые row locks и API schema не добавлялись: это отдельное
  concurrency-изменение для 6.6.

Вертикальный lifecycle slice 6.3b завершён:

- `ImportReviewLifecycleActor.apply()` содержит общие transition checks и
  mutations, но не делает `commit`/`rollback`;
- API `ImportReviewLifecycleService` владеет commit и rollback;
- chat преобразует callback сразу в typed `ImportReviewLifecycleAction`,
  передаёт актуальный статус queue item как `expected_status` и фиксирует claim
  action state вместе с lifecycle mutation одним commit;
- старый string-based `RawTransactionReviewStatusUseCase` и оставшаяся
  `imports/application/review` удалены;
- новых production-файлов и transaction abstractions не добавлялось.

Следующие actors выделяются в тех же модулях только для workflows, которые
действительно переиспользуются API и chat.

При фактическом change pressure создать один
`import_review/repository.py`, содержащий только review-specific persistence:

- загрузка/lock review row;
- expected-status write;
- link/unlink operation;
- duplicate evidence lookup;
- review transfer candidate lookup;
- affected document lookup.

Не создавать repository на каждую ORM-модель и не вводить `BaseRepository`.
Document upload, parse attempts, mapping и statement-processing writes остаются
в imports repositories.

#### Конкурентные проверки

Typed mutation command сохраняет:

- `workspace_id` через validated `WorkspaceContext`;
- `document_id` и `item_id`;
- `expected_status` для state-changing actions;
- `idempotency_key` для создания ledger operation;
- `expected_operation_id` для undo/link scenarios;
- fingerprint, если один idempotency key может получить разный payload.

Row и связанные operation records блокируются до финансовой mutation там, где
это требуется текущим contract.

#### Не меняется

- financial model `Operation 1 -> N MoneyEntry`;
- confirmed/ignored status semantics;
- deduplication algorithm;
- API error envelope;
- chat UX.

#### Проверки

- confirmation validation, conflicts и replay;
- lifecycle replay/conflict;
- transfer variants и affected documents;
- undo replay/conflict;
- rule application result;
- rollback при ожидаемой ошибке;
- отсутствие commit внутри transaction-neutral actors.

#### Exit

Все новые review mutations принадлежат `import_review`. Legacy confirmation,
transfer и lifecycle wrappers удалены; rule creation/application унифицированы
для React confirmation и chat.

### Commit 6.4 — Migrate React API composition

Статус: defining-module imports completed вместе с 6.3a; API contract checks
остаются отдельным шагом.

#### Проблема

API namespace уже называется `import_review`, но imports application classes
берутся из старого feature path.

#### Изменения

- переключить API dependencies на `app.features.import_review`;
- переключить mapper imports и request/response enum imports;
- оставить Pydantic HTTP schemas в `src/app/api/v1/import_review`;
- оставить `/api/v1/import-review/...` без изменений;
- сохранить permission check
  `can_manage_imports && can_write_financial_data`;
- внешний API application service делает commit/rollback вокруг actor.

Router остаётся HTTP adapter: строит command, переводит domain/application
errors в API errors и формирует response. Финансовых решений и commit в router
нет.

#### Проверки

- OpenAPI diff не содержит непредусмотренных изменений;
- auth/permission/not-found contracts;
- draft evaluation;
- lifecycle;
- confirmation и idempotent replay;
- три transfer variants;
- undo;
- apply rules;
- frontend type generation/check при изменении OpenAPI.

#### Exit

React Import Review использует только новый feature path. Публичный JSON
contract не изменился.

### Commit 6.5 — Migrate chat and remove legacy review

Статус: completed 2026-07-28.

#### Проблема

На старте chat использовал отдельные confirmation, transfer, lifecycle и rule
orchestration paths, из-за чего React и chat могли разойтись в поведении.

#### Изменения

- ~~заменить string-based `RawTransactionReviewCommand.action` typed
  commands;~~ completed 2026-07-28;
- ~~lifecycle callbacks переводить в `ImportReviewLifecycleAction`;~~ completed
  2026-07-28;
- ~~confirmation выполнять общим confirmation actor;~~ completed 2026-07-28;
- ~~transfer выполнять общим transfer actor;~~ completed 2026-07-28;
- ~~rule creation/application выполнять общим actor там, где совпадает
  contract;~~ completed через `ImportReviewRuleCreator` 2026-07-28;
- ~~сохранить consume action token и financial mutation в одной транзакции;~~
  completed для confirmation, transfer, lifecycle и rule creation 2026-07-28;
- ~~удалить `application/review/actions.py`;~~ completed 2026-07-28;
- ~~удалить `application/review/status.py`;~~ completed 2026-07-28;
- ~~удалить `RawTransactionReviewer` и legacy command/result;~~ completed
  2026-07-28;
- ~~удалить `RawTransactionReviewStatusUseCase`;~~ completed 2026-07-28.

Для chat confirmation state зафиксировать стабильные concurrency inputs:

- expected row status на момент показа действия;
- стабильный idempotency key для posting action.

Confirmation использует `ChatConversationState.id` как стабильный idempotency
key и статус заново прочитанного queue item как `expected_status`. Поэтому
расширять state payload и мигрировать старые активные состояния не потребовалось.
Lifecycle также использует актуальный статус queue item как `expected_status`;
idempotency key ему не нужен, потому что он не создаёт ledger records.

#### Проверки

- double click/action-token replay не создаёт вторую operation;
- stale expected status отклоняется;
- confirm через chat применяет те же confirmability rules, что React;
- duplicate/ignore/mark-unique используют lifecycle policy;
- transfer остаётся balanced и `affects_profit=false`;
- ошибка откатывает и chat state claim, и financial mutation;
- success сохраняет обе части одним commit.

#### Exit

В production нет legacy review dispatcher. React и chat используют одни и те
же import-review actors и policies.

### Commit 6.6 — Remove ledger back-dependency

#### Проблема

`RawTransactionPoster` и imported undo в ledger сами управляют imports:

- загружают/блокируют raw rows;
- проверяют import dedupe;
- связывают и отвязывают operation;
- пересчитывают document validation;
- меняют document status.

Это делает ledger зависимым от review workflow и создаёт двустороннюю
feature-связанность.

#### Изменения

Разделить текущий posting:

```text
ImportReview actor
  -> load/lock RawTransaction
  -> review validation and dedupe checks
  -> build ledger-owned posting command
  -> LedgerPostingService.post(...)
  -> link RawTransaction to Operation
  -> refresh imports document validation/status

LedgerPostingService
  -> validate ledger posting facts
  -> create Operation
  -> create MoneyEntry
  -> return committed-in-transaction Operation
```

Ledger-owned command/facts содержит только нужные финансовые данные:

- operation type/date/description;
- account and counterparty account;
- amount/currency/balance metadata;
- category/property references;
- source/audit metadata;
- idempotency key/fingerprint.

Он не принимает `RawTransaction`, `UploadedDocument` или
`ImportRepository`.

Для transfer import-review actor:

- блокирует одну или две raw rows;
- проверяет допустимость пары;
- передаёт ledger две сбалансированные entry facts;
- связывает обе rows с одной operation;
- обновляет все affected documents.

Для undo import-review actor:

- проверяет связь row/operation;
- просит ledger отменить или деактивировать posting по ledger rules;
- отвязывает affected raw rows;
- восстанавливает review statuses;
- обновляет affected documents.

Убрать imports application imports из ledger posting/undo. Type-only ORM
relationships между persistence models не являются причиной переносить
`RawTransaction` в `import_review`; их оценивают отдельно и не смешивают с
application boundary.

#### Связанные persistence изменения

Это точка, где разрешено вернуться к deferred Phase 4:

- перенести review-specific queries из broad `ImportRepository`;
- убрать raw-row parameters из ledger application/repository methods;
- оставить document/mapping persistence без изменений;
- не вводить generic CRUD.

Schema migration не нужна, если анализ implementation commit не выявит
недостающий constraint. Любое изменение constraint выполняется отдельным
commit с PostgreSQL tests.

#### Проверки

- income/expense posting создаёт прежние Operation и MoneyEntry;
- transfer entries балансируются в ноль;
- transfer не влияет на profit;
- raw row связывается только после успешного ledger posting;
- failure откатывает operation, entries, links и document state;
- undo обновляет все rows одного transfer;
- workspace isolation;
- confirmation idempotency;
- concurrent confirmation PostgreSQL characterization, если затрагиваются
  locks/constraints;
- repository-wide import search подтверждает отсутствие ledger application
  dependency на imports review/application.

#### Exit

- ledger posting не импортирует imports application/repository;
- ledger не обновляет RawTransaction или UploadedDocument;
- import-review application владеет полной orchestration;
- финансовая mutation остаётся атомарной.

## Порядок изменения тестов

Phase 6 меняет imports в тестах и добавляет недостающую characterization, но не
делает массовую реорганизацию test tree. Физический перенос и объединение
mega-files остаются Phase 7.

Минимальный набор по commit:

| Commit | Обязательные группы |
| --- | --- |
| 6.1 | classification, confirmability, lifecycle, queue |
| 6.2 | read model, duplicate evidence, transfer options, read API |
| 6.3 | confirmation, lifecycle mutations, transfers, rules, undo |
| 6.4 | полный import-review API contract |
| 6.5 | chat review actions, confirmation, transfers, transaction rollback |
| 6.6 | ledger posting/undo, imports integration, PostgreSQL concurrency |

Не добавлять tests, единственная цель которых — проверить:

- старый import path;
- compatibility re-export;
- что actor вызвал private helper;
- точное количество внутренних collaborators;
- структуру dataclass без observable contract.

## Инварианты на всём этапе

1. Parser и mapping не создают confirmed ledger records.
2. Raw source, attempts и raw rows не теряются.
3. Workspace filter сохраняется в каждом read/write.
4. Повторное confirmation не удваивает деньги.
5. Transfer всегда balanced и `affects_profit=false`.
6. Duplicate/ignored rows не влияют на ledger.
7. Undo не hard-delete confirmed financial history.
8. API routes и JSON values не меняются без отдельного решения.
9. Chat и API не расходятся в business rules.
10. Document validation пересчитывается после изменения review state.

## Что специально не делаем

- не меняем deduplication matching semantics;
- не добавляем parser versioning или reparse;
- не меняем database schema только ради нового package;
- не вводим event bus, CQRS storage или background queue;
- не создаём repository на каждую модель;
- не переносим `RawTransaction` persistence model из `imports`;
- не реорганизуем весь test suite до Phase 7;
- не меняем React UX и API paths;
- не добавляем abstractions «для будущих клиентов», кроме уже существующих
  React и chat.

## Stop conditions

Работу по конкретному commit нужно остановить и отдельно обсудить, если:

- требуется изменить пользовательский review flow;
- обнаружено различие React/chat, для которого неясен правильный contract;
- требуется новая database constraint или migration;
- невозможно сохранить atomicity chat state и financial mutation;
- file move начинает требовать broad generic repository/UoW;
- тест фиксирует поведение, противоречащее финансовым инвариантам.

## Definition of done

Phase 6 завершена, когда одновременно выполнено:

- существует `src/app/features/import_review`;
- pure review policies принадлежат его domain;
- read model и mutation actors принадлежат его application layer;
- React API использует новый feature;
- chat использует те же policies и mutation actors;
- legacy `RawTransactionReviewer` и status wrapper удалены;
- ledger posting принимает ledger facts и не управляет imports lifecycle;
- API contract не изменился;
- chat action и financial mutation атомарны;
- relevant Ruff, ty, imports, ledger, API и chat tests проходят;
- документация `imports` и `ledger` соответствует фактическим границам.
