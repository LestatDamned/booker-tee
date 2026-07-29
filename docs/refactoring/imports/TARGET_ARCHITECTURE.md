# Целевая архитектура Imports

Статус: единственный активный план и архитектурный ориентир.

Актуально на: 2026-07-29.

Этот документ фиксирует целевое устройство `imports` и карту перехода от
текущей структуры. Он отвечает на вопросы:

- какие обязанности остаются внутри `imports`;
- где находятся DTO, use cases, domain policies и persistence;
- куда перемещается каждый существующий модуль;
- какие файлы объединяются или удаляются;
- в каком порядке выполнять изменения без одновременной смены поведения.

Этот документ является source of truth для границ, целевого дерева,
последовательности миграции и её статуса. Завершённые планы, аудиты и test
cleanup strategy поглощены сюда; подробная история остаётся в Git.

## 1. Архитектурное решение

Для `imports` используется **feature-first структура с локальными слоями**.

Модуль достаточно сложен для явного разделения application, domain и
infrastructure responsibilities, но полная гексагональная структура в каждой
папке добавит больше файлов и интерфейсов, чем полезных границ. Глобальная
слоистая структура (`dto/`, `services/`, `repositories/`, `use_cases/`) также
не подходит: изменение одного сценария снова потребует навигации по всему
модулю.

Поэтому верхний уровень отражает продуктовые возможности:

```text
documents   жизненный цикл загруженного документа
statements  превращение выписки в reviewable raw transactions
parsers     распознавание известных банковских форматов
mapping     описание и импорт неизвестного табличного формата
```

Внутри возможности слой выделяется только когда он помогает чтению:

- `dto.py` — внутренние application values, не HTTP-схемы и не ORM;
- `commands/` — сценарии, меняющие состояние;
- `queries/` — сценарии чтения и их проекции;
- `repository.py` — SQLAlchemy queries и persistence mapping;
- pure policies и calculations лежат рядом с принадлежащей им возможностью;
- внешние форматы и файловый ввод остаются infrastructure adapters.

`import_review` остаётся отдельной feature. Он использует результат импорта, но
не является частью распознавания документа.

## 2. Текущее состояние и принятые решения

Уже выполнено:

- удалён неподтверждённый пользовательский reparse;
- unsigned amount больше не получает скрытый default `INCOME`;
- imports-specific SSR runtime удалён, compatibility redirects собраны вместе;
- statement validation использует один typed reason resolver и один persisted
  report decoder;
- `import_review` выделен в самостоятельную feature;
- React и chat используют общие review actors;
- ledger posting принимает готовые financial facts и не управляет import
  lifecycle;
- unknown-statement analysis уже прошёл первое безопасное укрупнение;
- shared parser primitives больше не зависят от application layer.

Фактическая граница сейчас:

```text
imports
  -> сохраняет документ и parse attempt
  -> извлекает и распознаёт исходные данные
  -> создаёт и валидирует reviewable RawTransaction
  -> хранит mapping templates и executions

import_review
  -> собирает очередь и evidence
  -> применяет lifecycle, classification и rules
  -> подтверждает income/expense/transfer
  -> связывает результат с ledger и выполняет undo
```

Текущие открытые риски:

| Priority | Проблема | Решение |
|---|---|---|
| P1 | Duplicate evidence хранится в `normalization_error`; `MARK_UNIQUE` может оставить строку заблокированной | Отдельный behavioral шаг после persistence ownership |
| P2 | Review reads/locks/status/linking остаются в broad imports repositories | Первым архитектурным шагом выделить ownership `ImportReviewRepository` |
| P2 | Persisted unknown-analysis JSON декодируется вручную | Один frozen Pydantic projection на JSON boundary |
| P2 | `ParseAttemptStatus` всё ещё определяется в ORM module | Перенести в documents-owned types при перестройке Documents |
| P2 | Широкие repositories смешивают document, statement, mapping и review queries | Разнести по capability после review persistence boundary |

Неисправленные названия, мелкие helpers, механические API mappings и
организация test tree не являются блокером начала архитектурной миграции.

## 3. Что архитектура не вводит

Рефакторинг не должен создавать:

- отдельные `domain/application/infrastructure` в каждой маленькой папке;
- `BaseRepository`, generic CRUD, service locator или глобальный DI container;
- интерфейс для каждого класса без второй реализации или значимой test seam;
- package facades с массовыми re-exports из `__init__.py`;
- дублирующие старую и новую реализации compatibility wrappers;
- новые HTTP DTO внутри feature: Pydantic-схемы API остаются в
  `src/app/api/v1/imports`;
- database migration: ORM aggregate пока остаётся в корневом `models.py`;
- общий parser pipeline, скрывающий существенные различия банков;
- изменение deduplication behavior одновременно с массовым перемещением файлов.

Гексагональный приём применяется точечно: `Protocol` нужен на границе parser,
storage или другого заменяемого adapter, но не как обязательная оболочка
каждого use case.

## 4. Целевое дерево

`__init__.py` опущены там, где не несут архитектурного смысла.

```text
src/app/features/imports/
├── __init__.py
├── models.py
├── types.py
├── documents/
│   ├── dto.py
│   ├── errors.py
│   ├── types.py
│   ├── lifecycle.py
│   ├── attempts.py
│   ├── validation_report.py
│   ├── storage.py
│   ├── repository.py
│   ├── commands/
│   │   ├── upload.py
│   │   └── manage.py
│   └── queries/
│       ├── list.py
│       └── detail.py
├── statements/
│   ├── dto.py
│   ├── process.py
│   ├── validation.py
│   ├── validation_service.py
│   ├── deduplication.py
│   ├── raw_transactions.py
│   └── repository.py
├── parsers/
│   ├── protocol.py
│   ├── registry.py
│   ├── extractors/
│   │   ├── dto.py
│   │   ├── resolver.py
│   │   ├── pdf.py
│   │   └── xlsx.py
│   ├── support/
│   │   ├── common.py
│   │   ├── headers.py
│   │   └── normalization.py
│   └── banks/
│       ├── alfabank.py
│       ├── expobank.py
│       ├── ozon_bank.py
│       ├── sberbank.py
│       ├── tbank.py
│       └── vtb/
│           ├── card.py
│           ├── deposit.py
│           └── shared.py
└── mapping/
    ├── dto.py
    ├── errors.py
    ├── engine.py
    ├── rows.py
    ├── raw_transactions.py
    ├── raw_tables.py
    ├── control_totals.py
    ├── validation.py
    ├── repository.py
    ├── commands/
    │   └── import_rows.py
    ├── queries/
    │   ├── overview.py
    │   ├── preview.py
    │   └── source_rows.py
    ├── templates/
    │   ├── defaults.py
    │   ├── codec.py
    │   └── matching.py
    └── analysis/
        ├── dto.py
        ├── analyzer.py
        ├── tables.py
        ├── columns.py
        ├── text_tables.py
        ├── control_totals.py
        ├── hints.py
        ├── unknown_statement_hints.json
        └── values.py
```

Это целевой ориентир, а не требование создать пустой файл под каждое имя.
Если после объединения ответственность остаётся небольшой и cohesive, соседние
файлы могут остаться одним модулем.

## 5. Направление зависимостей

```text
Imports API
  ├── documents commands / queries
  └── mapping commands / queries

documents.upload
  -> statements.process
       ├── parsers: известный формат
       └── mapping analysis/template path: неизвестный формат
              |
              v
       RawTransactionDraft
              |
              v
       statements validation / deduplication / repository

Import Review API / chat
  -> import_review application
  -> import_review repository
  -> ledger posting / transaction rules
  -> narrow imports validation and document-status collaborators
```

Обязательные правила:

1. `imports` не импортирует `import_review`.
2. Parser не импортирует FastAPI, ORM models или review application.
3. Известный parser и неизвестный mapping сходятся в одном
   `RawTransactionDraft`.
4. Repository выполняет queries и persistence mapping, но не принимает
   продуктовые решения.
5. Commands владеют транзакционным workflow; DTO не выполняют логику.
6. API преобразует HTTP-схемы в application values на своей границе.
7. `import_review` владеет row locks, review queue, confirmation links и review
   status mutations.

## 6. Значение основных файлов

### `models.py`

Содержит только SQLAlchemy persistence models общего import aggregate:
`UploadedDocument`, `ParseAttempt`, `RawTransaction`, mapping templates и
связанные persistence entities. Разбивать модели по capability сейчас не нужно:
это создаст import cycles и не уменьшит сложность использования aggregate.

### `types.py`

Корневой файл содержит только стабильные persisted values, используемые
несколькими capabilities, прежде всего `RawTransactionStatus` и
`UploadedDocumentStatus`.

Documents-owned `UploadedDocumentSource`, `UploadedDocumentType` и
`ParseAttemptStatus` переходят в `documents/types.py`. Тип, принадлежащий только
statements или mapping, переносится в соответствующий `dto.py` либо pure policy
module.

### Ошибки

Текущий общий `imports/errors.py` удаляется после распределения:

- upload и document-management errors → `documents/errors.py`;
- unknown mapping/import errors → `mapping/errors.py`;
- `RawTransactionReviewError` → `import_review/errors.py`.

API продолжает переводить application errors в HTTP responses на своей
границе. Feature errors не содержат HTTP status codes.

### `dto.py`

Содержит immutable или validation-oriented application data:

- command input;
- query projection;
- parser/mapping result;
- промежуточный typed boundary.

DTO не содержит SQLAlchemy entities, `Request`, `UploadFile`, HTTP status codes
или repository calls. Pydantic используется там, где данные пересекают
недоверенную или persisted JSON boundary; внутренний простой value может быть
dataclass.

### `commands/` и `queries/`

Это не механическое CQRS. Папки появляются только там, где несколько сценариев
чтения и изменения уже создают навигационный шум.

- command оркестрирует mutation, transaction и вызовы policies/adapters;
- query собирает read model без mutation;
- небольшая pure функция не превращается в use-case class только ради слоя.

### `repository.py`

Repository группируется по владельцу поведения, а не по ORM table:

- `documents/repository.py` — document lifecycle и parse attempts;
- `statements/repository.py` — raw row persistence, dedupe lookups,
  superseding;
- `mapping/repository.py` — templates, executions, source rows;
- `import_review/repository.py` — review queue, locks, classification,
  confirmation/linking.

Текущие широкие `imports/repository.py` и `query_repository.py` после
распределения методов удаляются.

## 7. Карта перемещений: Documents

| Сейчас | Цель | Причина |
|---|---|---|
| `application/documents/listing.py` | `documents/dto.py`, `documents/queries/list.py` | Отделить проекции от query orchestration |
| `application/documents/detail_reading.py` | `documents/dto.py`, `documents/queries/detail.py` | Явный read use case |
| `application/documents/snapshot.py` | `documents/dto.py`, `documents/repository.py` | Snapshot — persistence projection |
| `application/documents/validation_report.py` | `documents/validation_report.py` | Typed persisted validation boundary |
| `application/documents/upload.py` | `documents/commands/upload.py` | Главный mutation workflow |
| `application/documents/management.py` | `documents/commands/manage.py` | Delete/status management |
| `application/documents/parse_attempts.py` | `documents/attempts.py` | Cohesive lifecycle policy |
| `application/documents/status.py`, `domain/document_lifecycle.py` | `documents/lifecycle.py` | Один владелец status transitions |
| `infrastructure/storage.py` | `documents/storage.py` | Storage принадлежит document capability |
| document enums из `models.py` | `documents/types.py` | Persisted values не принадлежат ORM module |
| upload/document errors из `errors.py` | `documents/errors.py` | Ошибки рядом с owning capability |

В `documents/repository.py` переходят:

- создание document и parse attempt;
- workspace-scoped document lock;
- document/attempt status transitions;
- document cleanup;
- узкие list/detail persistence projections.

Текущий тяжёлый `get_document_for_workspace` не должен оставаться универсальной
загрузкой aggregate. Он разделяется минимум на узкий document snapshot и
review-specific loader, причём второй принадлежит `import_review`.

## 8. Карта перемещений: Statements

| Сейчас | Цель | Причина |
|---|---|---|
| processing/known pipeline/unknown fallback/attempt review | `statements/process.py` | Один читаемый orchestration path |
| `domain/control_totals.py` | `statements/dto.py` | Statement result values |
| `domain/validation.py`, `domain/validation_reason.py` | `statements/validation.py` | Один validation policy boundary |
| `pipelines/document_validation.py` | `statements/validation_service.py` | I/O orchestration отдельно от pure policy |
| domain и application dedupe modules | `statements/deduplication.py` | Один владелец duplicate evidence |
| `mapping/raw_transaction_mapper.py` | `statements/raw_transactions.py` | Общая сборка persisted raw row |
| `RawTransactionDraft` из parser types | `statements/dto.py` | Общий результат parser и mapping |

В `statements/repository.py` переходят:

- batch creation raw transactions;
- document/workspace-scoped dedupe lookups;
- superseding mapped rows;
- persistence данных, необходимых statement processing.

`review_messages.py` остаётся временным compatibility code только до отделения
duplicate evidence от `normalization_error`, после чего удаляется.

## 9. Карта перемещений: Parsers

Текущий parser code сохраняет своё поведение. Первая цель — сделать местоположение
предсказуемым, не унифицировать банковские алгоритмы.

| Сейчас | Цель |
|---|---|
| parser interface и result types | `parsers/protocol.py`, `statements/dto.py` |
| parser selection | `parsers/registry.py` |
| extraction DTO | `parsers/extractors/dto.py` |
| extraction resolver | `parsers/extractors/resolver.py` |
| PDF/XLSX extraction adapters | `parsers/extractors/pdf.py`, `xlsx.py` |
| общие parser helpers | `parsers/support/common.py` |
| header recognition | `parsers/support/headers.py` |
| текстовая нормализация | `parsers/support/normalization.py` |
| dedupe hash helper | `statements/deduplication.py` |

Однофайловые bank packages становятся файлами в `parsers/banks/`. `vtb`
остаётся подпакетом, поскольку уже содержит несколько связанных форматов и
общую реализацию.

После миграции consumers удаляются:

- неиспользуемый parser-local `MoneyDirection`;
- test-only aliases вроде `ExtractedPdf`;
- специализированный `UploadStorage.save_pdf`, если все callers используют
  общий `save_upload`.

## 10. Карта перемещений: Mapping

| Сейчас | Цель |
|---|---|
| mapping models и read models | `mapping/dto.py` |
| mapping engine | `mapping/engine.py` |
| row mapping | `mapping/rows.py` |
| draft conversion | `mapping/raw_transactions.py` |
| raw table handling | `mapping/raw_tables.py` |
| mapping control totals | `mapping/control_totals.py` |
| mapping validation | `mapping/validation.py` |
| import use case | `mapping/commands/import_rows.py` |
| reader | `mapping/queries/overview.py`, `preview.py`, `source_rows.py` |
| mapping defaults | `mapping/templates/defaults.py` |
| template serialization | `mapping/templates/codec.py` |
| template signatures/use | `mapping/templates/matching.py` |
| mapping errors из `errors.py` | `mapping/errors.py` |

`template_use_case.py` удаляется после переноса callers к конкретным command или
matching actors. Untyped `values.py` объединяется с typed template codec, если
это одна сериализационная ответственность.

### Unknown statement analysis

| Сейчас | Цель |
|---|---|
| analysis models | `mapping/analysis/dto.py` |
| analyzer | `mapping/analysis/analyzer.py` |
| column profiles и suggestions | `mapping/analysis/columns.py` |
| table analysis/detection/continuations | `mapping/analysis/tables.py` |
| text table extraction | `mapping/analysis/text_tables.py` |
| control total detection | `mapping/analysis/control_totals.py` |
| hints и JSON data | `mapping/analysis/hints.py` и JSON рядом |
| value detectors | `mapping/analysis/values.py` |
| fallback orchestration | `statements/process.py` |

Persisted JSON analysis декодируется один раз в Pydantic projection. Ручные
цепочки `cast`, `isinstance`, `.get()` и повторные API mappings после этого
удаляются.

В `mapping/repository.py` находятся template CRUD, matching signatures,
mapping executions, idempotency и source-row queries. Review status/locking в
него не входят.

## 11. Целевая структура Import Review

`import_review` не переносится обратно в `imports`. Его структура постепенно
становится:

```text
src/app/features/import_review/
├── errors.py
├── repository.py
├── application/
│   ├── commands/
│   │   ├── confirmation.py
│   │   ├── lifecycle.py
│   │   ├── rules.py
│   │   ├── transfers.py
│   │   └── undo.py
│   └── queries/
│       ├── classification.py
│       ├── duplicates.py
│       ├── review.py
│       ├── transfer_options.py
│       ├── transfer_suggestions.py
│       └── validation.py
└── domain/
    └── текущие cohesive policies
```

В `ImportReviewRepository` переходят:

- получение и блокировка review row;
- review queue и attention counts;
- duplicate candidate reads;
- confirmed-operation hash checks;
- transfer candidate reads;
- classification/status/link mutations.

Это устраняет forwarding между широкими imports repositories и возвращает
persistence тому feature, который принимает решение.

### Транзакционная модель

Самый внешний application workflow владеет `commit` и `rollback`.

```text
HTTP service
  -> transaction-neutral actor
  -> commit

Chat use case
  -> claim action token
  -> тот же transaction-neutral actor
  -> один общий commit
```

Actor может выполнять `flush`, но не делает `commit` или `rollback` и не знает
об HTTP/chat state. Repository также не делает commit. Router строит command и
преобразует errors, но не владеет financial mutation.

Для confirmation, transfer и lifecycle этот контракт уже реализован и должен
сохраниться при физическом перемещении файлов. Generic Unit of Work или event
bus для синхронной mutation не нужен.

## 12. Где сокращается код

Само перемещение файлов не уменьшает LOC. Сокращение возникает из удаления
переходных и дублирующих слоёв:

1. удалить `template_use_case.py`;
2. объединить template values и codec;
3. удалить неиспользуемый parser `MoneyDirection`;
4. удалить test-only extraction aliases после миграции тестов;
5. удалить `save_pdf` после перехода на `save_upload`;
6. объединить раздробленные known/unknown process modules;
7. объединить analysis modules с одной причиной изменения;
8. удалить `review_messages.py` после исправления duplicate evidence;
9. заменить повторный ручной JSON decoding одной typed boundary;
10. удалить repository forwarding и старые broad repositories;
11. не оставлять import compatibility facades после внутренних moves.

Снимок на 2026-07-29:

```text
imports        90 Python-файлов, 11 574 строк
import_review  20 Python-файлов,  3 117 строк
```

Ориентир после безопасных объединений — примерно 55–65 содержательных
Python-файлов внутри `imports`. Это не KPI: cohesive файл не дробится и не
сливается ради числа.

## 13. Стратегия выполнения

Не нужно сначала полировать весь код в старой структуре. Перед moves нужен
только safety gate:

1. текущие Ruff, ty и профильные tests имеют известный baseline;
2. financial/data invariants защищены characterization tests;
3. behavioral fix выполняется отдельно от file move;
4. при переносе capability старый путь удаляется в том же change set.

Допустимо исправлять во время capability move:

- ownership и направление dependencies;
- имена, переставшие соответствовать ответственности;
- forwarding wrappers и дублирующие adapters;
- DTO/JSON boundary, непосредственно мешающие новой границе;
- cohesion файлов, которые уже перемещаются.

До завершения структуры откладываются:

- массовая косметическая чистка функций;
- полная реорганизация test tree;
- объединение алгоритмов bank parsers;
- общие abstractions без повторяющегося стабильного контракта;
- оптимизация кода, который ещё может быть удалён.

## 14. Последовательность миграции

### Шаг 0. Зафиксировать границы

- этот документ принят как единственный target;
- старые refactoring plans поглощены и удалены;
- README указывает текущий шаг и не повторяет архитектуру;
- baseline checks и characterization risks известны.

### Шаг 1. Persistence ownership

- перенести review reads, locks и mutations в `ImportReviewRepository`;
- удалить forwarding methods;
- оставить document и mapping queries в их владельцах.

Это первый важный шаг: после него физические moves не закрепят неправильную
зависимость.

### Шаг 2. Duplicate evidence

- добавить overlapping-statement characterization;
- отделить duplicate signal от `normalization_error`;
- закрепить `MARK_UNIQUE` и `MARK_DUPLICATE`;
- проверить PostgreSQL confirmation race.

Это отдельный behavioral change set. Он выполняется до переноса statements,
чтобы новая структура не закрепляла ошибочную модель duplicate evidence.

### Шаг 3. Documents

- выделить DTO и list/detail queries;
- собрать lifecycle и attempts;
- выделить document repository;
- перенести storage;
- распределить document types и errors;
- удалить исходные файлы в том же change set.

### Шаг 4. Statements

- ввести общий `RawTransactionDraft`;
- собрать process orchestration;
- объединить validation и deduplication ownership;
- выделить statement repository.

### Шаг 5. Parsers и extractors

- выполнить преимущественно механические moves;
- обновить defining-module imports;
- удалить aliases после обновления тестов;
- не менять bank-specific parsing behavior.

### Шаг 6. Typed unknown-analysis boundary

- описать persisted JSON через Pydantic;
- декодировать его один раз;
- сократить defensive decoding и изоморфные API mappings.

### Шаг 7. Mapping

- разделить commands и queries;
- собрать template responsibilities;
- объединить мелкие analysis modules;
- удалить старые wrappers.

### Шаг 8. Import Review commands/queries

- сгруппировать существующие actors по mutation/read intent;
- сохранить domain policies отдельными только при самостоятельной
  ответственности.

### Шаг 9. Удаление старой структуры

- удалить пустые `application/documents`, `pipelines`, старые mapping/parser
  paths и broad repositories;
- обновить тестовые импорты и архитектурную документацию;
- не оставлять две точки входа к одному use case.

### Шаг 10. Post-architecture cleanup

- физически разложить tests по новым capabilities;
- удалить implementation-detail и wrapper tests только после проверки риска;
- сократить изоморфные API mappings;
- пересмотреть оставшиеся маленькие helpers и названия;
- обновить module-level architecture documentation.

### Шаг 11. Parser normalization

- сохранить отдельный fixture contract для каждого банка;
- объединять только доказанно одинаковый parsed-fields → draft переход;
- не вводить plugin framework без нового реального extension scenario.

Текущий статус:

| Шаг | Статус |
|---|---|
| 0. Documentation consolidation | completed 2026-07-29 |
| Safety baseline | next |
| 1. Persistence ownership | after baseline |
| 2–11 | pending |

## 15. Gate для каждого шага

Каждый change set:

1. сохраняет workspace boundaries и transaction ownership;
2. сначала обновляет consumers, затем удаляет старый модуль;
3. не добавляет facade без реального внешнего consumer;
4. проходит `ruff check`, `ty check` и релевантные import tests;
5. отдельно фиксирует намеренное изменение поведения;
6. не оставляет параллельные реализации.

Минимальные группы проверок:

```text
documents
  -> upload, parse failure, source preservation, workspace isolation

statements
  -> parser fixtures, validation, deduplication, raw-row preservation

mapping
  -> preview/import parity, validation, idempotency

import_review
  -> lifecycle, confirmation, transfer, undo, API/chat parity

PostgreSQL
  -> concurrency, constraints, duplicate and idempotency races
```

Обязательные risk tests не удаляются:

- transfer balanced и `affects_profit=false`;
- confirmation создаёт ledger records ровно один раз;
- workspace isolation;
- upload/mapping/confirmation idempotency;
- raw document, attempts, text/tables и rows сохраняются;
- parser failure сохраняет document и attempt;
- delete/ignore не повреждают linked/confirmed records;
- undo атомарно согласует ledger и review;
- API не раскрывает sensitive source data.

Архитектурная миграция завершена, когда:

- `imports` не импортирует `import_review`;
- review repository владеет locks, queue, status и ledger links;
- documents repository не загружает review-specific graph;
- parsers не импортируют FastAPI и ORM;
- parser и mapping возвращают один `RawTransactionDraft`;
- persisted JSON имеет единственный typed decoder;
- HTTP DTO остаются в API layer;
- широких `imports/repository.py` и `query_repository.py` больше нет;
- старые пути и compatibility wrappers удалены;
- структура README совпадает с фактической структурой кода.

## 16. Отложенный backlog

После достижения целевого дерева повторно оценить:

- организацию test suite по фактическим capabilities;
- повторяющиеся API permission/error contract tests;
- большие unknown mapping tests и mega-file `test_imports.py`;
- изоморфные Pydantic/API transformations;
- parser normalization;
- локальные naming и line-count cleanup;
- legacy ledger read-only projection, которая пока читает `RawTransaction`;
- необходимость дальнейшего дробления `models.py`.

Backlog не является причиной откладывать архитектурные moves. Пункт удаляется,
если новый layout устранил проблему естественным образом.

## 17. История ключевых решений

| Дата | Решение |
|---|---|
| 2026-07-27 | Удалён speculative user reparse |
| 2026-07-28 | Завершён React imports cutover и удалён imports SSR runtime |
| 2026-07-28 | Domain validation/deduplication dependencies направлены от persistence |
| 2026-07-28 | Упрощён unknown-statement analysis без изменения алгоритмов |
| 2026-07-28 | `import_review` выделен; API/chat используют общие actors |
| 2026-07-28 | Ledger больше не управляет import-review mutation |
| 2026-07-29 | Feature-first target принят как единственный активный план |

Подробности завершённых implementation plans доступны в Git history и не
поддерживаются как параллельная активная документация.

## 18. Правило принятия локальных решений

Если фактический код не укладывается в указанное имя файла, решение принимается
по ответственности, а не по симметрии дерева:

1. у кода один владелец поведения;
2. зависимости направлены к устойчивым domain/application contracts;
3. query не выполняет mutation;
4. repository не решает бизнес-политику;
5. объединение уменьшает навигацию, не создавая god module;
6. новый abstraction появляется только из повторяющегося стабильного
   контракта.

Это важнее буквального совпадения с эскизом дерева.
