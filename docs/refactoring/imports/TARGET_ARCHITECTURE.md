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

- `dto.py` — внутренние immutable Pydantic application models, не HTTP-схемы
  и не ORM;
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
| P2 | Stored unknown-analysis JSON декодируется вручную | Один frozen Pydantic projection на JSON boundary |
| P2 | `ParseAttemptStatus` всё ещё определяется в ORM module | Перенести в documents-owned types при перестройке Documents |
| P2 | Imports repositories всё ещё смешивают document, statement и mapping persistence | Разнести по capability на шагах 3, 4 и 7 |

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
│   ├── types.py
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
│   │   ├── drafts.py
│   │   ├── headers.py
│   │   └── normalization.py
│   ├── alfabank.py
│   ├── expobank.py
│   ├── ozon_bank.py
│   ├── sberbank.py
│   ├── tbank.py
│   └── vtb/
│       ├── card.py
│       ├── deposit.py
│       └── statement_period.py
└── mapping/
    ├── dto.py
    ├── errors.py
    ├── engine.py
    ├── rows.py
    ├── drafts.py
    ├── raw_tables.py
    ├── control_totals.py
    ├── validation.py
    ├── templates.py
    ├── repository.py
    ├── commands/
    │   └── import_rows.py
    ├── queries/
    │   ├── overview.py
    │   ├── preview.py
    │   └── source_rows.py
    └── analysis/
        ├── dto.py
        ├── analyzer.py
        ├── tables.py
        ├── columns.py
        ├── text_tables.py
        ├── hints.py
        └── unknown_statement_hints.json
```

Это целевой ориентир, а не требование создать пустой файл под каждое имя.
Если после объединения ответственность остаётся небольшой и cohesive, соседние
файлы могут остаться одним модулем. В частности, template defaults, codec и
signature matching сначала собираются в одном `templates.py`. Делить его можно
только после появления нескольких самостоятельных причин изменения.

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
или repository calls. Все application data по умолчанию описываются Pydantic-
моделями на общей immutable базе. `dataclass` остаётся только для
runtime-композиции зависимостей или технического состояния, которое не
валидируется, не сериализуется и не пересекает application boundary.

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
| document enums из `models.py` | `documents/types.py` | Stored values не принадлежат ORM module |
| upload/document errors из `errors.py` | `documents/errors.py` | Ошибки рядом с owning capability |

Step 3A завершён 2026-07-29: первые три перемещения выполнены без package
re-export facades. `query_repository.py` удалён целиком; list/detail/snapshot
reads принадлежат `DocumentRepository`, DTO отделены от query orchestration.
Существующий `ImportRepository.get_document_for_workspace` временно делегирует
read новому владельцу для ещё не перенесённых write workflows и удалён в 3B.

Step 3B завершён 2026-07-29: document/attempt write persistence, workspace lock,
lifecycle, attempts и document-owned enums принадлежат `documents`.
`ImportRepository` больше не содержит document reads или lifecycle mutations.

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
| processing и known pipeline | `statements/process.py` | Один читаемый orchestration path |
| `pipelines/attempt_review.py` | `documents/attempts.py` | Review-required transition принадлежит document/attempt lifecycle |
| `domain/control_totals.py` | `statements/dto.py` | Statement result values |
| `domain/validation.py`, `domain/validation_reason.py` | `statements/validation.py` | Один validation policy boundary |
| `pipelines/document_validation.py` | `statements/validation_service.py` | I/O orchestration отдельно от pure policy |
| domain и application dedupe modules | `statements/deduplication.py` | Один владелец duplicate evidence |
| `mapping/raw_transaction_mapper.py` | `statements/raw_transactions.py` | Общая сборка persisted raw row |
| `RawTransactionDraft` из parser types | `statements/dto.py` | Общий результат parser и mapping |
| `domain/types.py` | `documents/types.py`, `statements/types.py` | Статусы разделены по owning capability |

В `statements/repository.py` переходят:

- batch creation raw transactions;
- document/workspace-scoped dedupe lookups;
- superseding mapped rows;
- persistence данных, необходимых statement processing.

`review_messages.py` удалён на Step 2. Duplicate detection меняет только status,
структурированное evidence строится review read model, а `normalization_error`
содержит только ошибки преобразования исходных данных.

Step 4 завершён 2026-07-29. Parse-success workflow теперь читается через
`StatementParseCompletionService.complete_successful_attempt()`, известный
формат — через `KnownStatementImportPipeline.import_parsed_transactions()`.
Actor-oriented `Class.action` API сохранён для mapper, policy, deduplicator,
validation service и repositories. Общий `ImportRepository` удалён и разделён
на `StatementRepository` и `MappingRepository`.

После Step 4 пакет `imports` уменьшился с 92 до 87 Python-файлов и с 10 989 до
10 949 строк production Python: минус 5 файлов и 40 строк без compatibility
facades.

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
| draft building helpers | `parsers/support/drafts.py` |
| header recognition | `parsers/support/headers.py` |
| текстовая нормализация | `parsers/support/normalization.py` |
| dedupe hash helper | временно `parsers/support/normalization.py`, ownership cleanup на Step 11 |

Однофайловые bank packages становятся файлами непосредственно в `parsers/`:
промежуточный каталог `banks/` не добавляет полезной информации. `vtb`
остаётся подпакетом, поскольку уже содержит несколько связанных форматов и
общую реализацию.

После миграции consumers удаляются:

- неиспользуемый parser-local `MoneyDirection`;
- test-only aliases вроде `ExtractedPdf`;
- специализированный `UploadStorage.save_pdf` — удалён на Step 3C после
  перевода tests на общий `save_upload`.

Step 5A завершён 2026-07-29: protocol, registry и extraction adapters находятся
в `parsers/`; canonical API использует
`BankStatementParser.matches_statement()`,
`BankStatementParser.parse_transaction_drafts()` и
`StatementParserRegistry.find_matching_parser()`. PDF-only aliases удалены,
bank-specific parsing behavior не менялось. Число файлов пока не изменилось,
production Python уменьшился с 10 949 до 10 937 строк.

Step 5B завершён 2026-07-29: общий parser support перенесён из
`parsing/support/` в `parsers/support/`. Неопределённые имена `common.py`,
`header_fields.py`, `cell`, `extracted_text` и `parse_with_error` заменены на
`drafts.py`, `headers.py`, `row_cell`, `extracted_statement_text` и
`parse_or_record_error`. Старый support path удалён без compatibility facade.
Число Python-файлов осталось 87; production Python вырос на две строки из-за
форматирования более явных вызовов.

Step 5C завершён 2026-07-29: одноформатные bank packages превращены в
`parsers/alfabank.py`, `expobank.py`, `ozon_bank.py`, `sberbank.py` и
`tbank.py`. VTB остаётся cohesive package с `card.py`, `deposit.py` и
переименованным `statement_period.py`. Registry и tests импортируют реализации
из defining modules; compatibility re-exports не добавлялись. Число
Python-файлов уменьшилось с 87 до 82, production Python осталось 10 939 строк.

Step 5D завершён 2026-07-29: последние source-файлы исторического `parsing/`
удалены. Финальный аудит не обнаружил старых parser imports, compatibility
facades, parser-local `MoneyDirection` или зависимостей `parsers` от FastAPI,
SQLAlchemy, ORM и application modules. Feature README синхронизирован с
capability-first структурой. Число Python-файлов уменьшилось с 82 до 80,
production Python — с 10 939 до 10 938 строк. Step 5 закрыт.

## 10. Карта перемещений: Mapping

| Сейчас | Цель |
|---|---|
| mapping models и read models | `mapping/dto.py` |
| mapping engine | `mapping/engine.py` |
| row mapping | `mapping/rows.py` |
| mapped rows → `RawTransactionDraft` | `mapping/drafts.py` |
| raw table handling | `mapping/raw_tables.py` |
| mapping control totals | `mapping/control_totals.py` |
| mapping validation | `mapping/validation.py` |
| import use case | `mapping/commands/import_rows.py` |
| reader | `mapping/queries/overview.py`, `preview.py`, `source_rows.py` |
| mapping defaults, serialization и signatures/use | `mapping/templates.py` |
| mapping errors из `errors.py` | `mapping/errors.py` |

`template_use_case.py` удаляется после переноса callers к конкретным command или
template actors. `values.py` объединяется с `templates.py`: отдельный модуль для
одного JSON integer decoder не имеет самостоятельной ответственности.

### Unknown statement analysis

| Сейчас | Цель |
|---|---|
| analysis models | `mapping/analysis/dto.py` |
| analyzer | `mapping/analysis/analyzer.py` |
| column profiles, suggestions и value detectors | `mapping/analysis/columns.py` |
| table analysis/detection/continuations | `mapping/analysis/tables.py` |
| text table extraction | `mapping/analysis/text_tables.py` |
| hints, control total detection и JSON data | `mapping/analysis/hints.py` и JSON рядом |
| fallback orchestration | `statements/process.py` |

Stored JSON analysis декодируется один раз в Pydantic projection. Ручные
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
5. удалить `save_pdf` после перехода на `save_upload` — выполнено на Step 3C;
6. объединить раздробленные known/unknown process modules;
7. объединить analysis modules с одной причиной изменения;
8. удалить `review_messages.py` после исправления duplicate evidence — выполнено
   на Step 2;
9. заменить повторный ручной JSON decoding одной typed boundary;
10. удалить repository forwarding и старые broad repositories;
11. не оставлять import compatibility facades после внутренних moves.

Baseline до архитектурных moves, 2026-07-29:

```text
imports        90 Python-файлов, 11 574 строк
import_review  20 Python-файлов,  3 117 строк
```

После Step 1 ownership перераспределён без изменения количества файлов:
`imports` — 11 070 строк, `import_review` — 3 651 строк. Общий объём production
code практически не изменился; целью шага было направление dependencies, а не
LOC reduction.

После Step 2 `imports` содержит 89 Python-файлов и 11 024 строки, а
`import_review` — 20 файлов и 3 649 строк. Удалены строковые duplicate messages,
однополевая `DuplicateDecision` и compatibility helper; migration БД не
потребовалась.

После Step 3A `imports` содержит 91 Python-файл и 10 994 строки. Два package
entrypoint добавлены ради явной границы `documents/queries`, но общий production
code сократился на 30 строк за счёт удаления повторных DTO и list forwarding.

После Step 3B количество файлов не изменилось, `imports` содержит 11 013 строк.
Явные зависимости `DocumentRepository` добавили 19 строк orchestration, при
этом широкий `ImportRepository` сократился с 279 до 162 строк и полностью
освобождён от document lifecycle persistence.

После Step 3C `imports` содержит 92 Python-файла и 10 989 строк. Новый
`documents/errors.py` добавил один явный ownership boundary, а удаление
`save_pdf`, PDF-only sanitizer и старого `application/documents` сократило
production code на 24 строки.

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

- добавить overlapping-statement characterization — выполнено;
- отделить duplicate signal от `normalization_error` — выполнено;
- закрепить `MARK_UNIQUE` и `MARK_DUPLICATE` — выполнено;
- проверить PostgreSQL confirmation race — выполнено через recovery и partial
  unique-index characterization.

Это отдельный behavioral change set. Он выполняется до переноса statements,
чтобы новая структура не закрепляла ошибочную модель duplicate evidence.

### Шаг 3. Documents

- выделить DTO и list/detail queries — выполнено в 3A;
- удалить `query_repository.py` и перевести read consumers — выполнено в 3A;
- собрать lifecycle и attempts — выполнено в 3B;
- дополнить document repository write-side persistence — выполнено в 3B;
- перенести document-owned enums в `documents/types.py` — выполнено в 3B;
- перенести storage — выполнено в 3C;
- распределить document types и errors — выполнено в 3B/3C;
- перенести commands и validation boundary — выполнено в 3C;
- удалить исходные файлы в том же change set — выполнено.

### Шаг 4. Statements

- ввести общий `RawTransactionDraft` — выполнено;
- собрать process orchestration — выполнено;
- объединить validation и deduplication ownership — выполнено;
- выделить statement repository — выполнено;
- разделить document/statement statuses — выполнено;
- удалить старые application/domain пути и широкий repository — выполнено.

### Шаг 5. Parsers и extractors

- 5A: перенести protocol, registry и extractors — выполнено;
- 5A: обновить canonical actor method names — выполнено;
- 5A: удалить extraction aliases после обновления тестов — выполнено;
- 5B: перенести и переименовать parser support — выполнено;
- 5C: переместить bank parsers и сократить однофайловые packages — выполнено;
- 5D: удалить оставшиеся старые пути и выполнить финальный cleanup — выполнено;
- не менять bank-specific parsing behavior.

### Шаг 6. Typed unknown-analysis boundary

- 6A: описать обе stored-формы `validation_report_json` через immutable
  Pydantic-модели — выполнено;
- 6B: декодировать report один раз на documents read boundary и передавать
  typed snapshot — выполнено;
- 6C: перевести mapping consumers на typed attributes, удалить локальные
  `dict.get`/`isinstance` decoders и сократить изоморфные API mappings —
  выполнено.

6A не меняет JSONB-схему, parser output или API. Существующий
`documents/validation_report.py` теперь является единственным владельцем
forward-compatible stored contract для:

- обычного statement validation report;
- balance-chain validation;
- unknown-statement table previews;
- column candidates и mapping suggestions.

После 6B `DocumentRepository` вызывает
`StoredValidationReport.model_validate(...)` при создании parse-attempt
snapshot. Document snapshot переиспользует тот же typed report, поэтому detail
и другие read consumers не декодируют JSON повторно.

После 6C mapping default resolver и mapping reader используют
`StoredTablePreview`, `StoredMappingSuggestion` и вложенные typed values
напрямую. Временный `model_dump(mode="json")` и локальные defensive decoders
удалены. Сборка `StatementMappingSpec` из analyzer suggestion имеет одного
владельца: `StatementMappingDefaultResolver.suggested_spec(...)`.

В API явными остались только преобразования с реальной семантикой:
zero-based/one-based индексы, warning field names и control-total references.
Изоморфные DTO → response schema преобразования используют Pydantic
`model_validate(..., from_attributes=True)`.

### Шаг 7. Mapping

Mapping рассматривается как одна capability, включающая анализ неизвестной
таблицы, preview, templates и импорт сопоставленных строк. До начала шага
реализация была разделена между:

- `application/unknown_statement_mappings/` (удалён в 7C);
- `application/unknown_statements/`;
- почти пустым на тот момент `mapping/`.

До начала шага это 31 Python-файл и 4 370 строк. Цель этапа — один canonical
root `mapping/`, ориентировочно 22–24 Python-файла и отсутствие старых import
paths. Уменьшение количества строк не является отдельным KPI: оно должно
получиться из удаления wrappers, повторной orchestration и лишних границ, а не
из уплотнения читаемого кода.

#### 7A. Core ownership

- перенести DTO, engine, row mapping, raw tables, draft building,
  control totals и validation в canonical `mapping/`;
- перенести mapping-specific errors в `mapping/errors.py`;
- сохранить `Class.action` и поведение, убрав из actor names избыточный
  `UnknownStatement` после переноса в однозначный `mapping/`;
- переименовать draft actor в
  `StatementMappingDraftBuilder.build_rows(...)`;
- обновить consumers напрямую, без compatibility facades и package re-exports;
- не считать отсутствие сокращения строк на этом механическом шаге проблемой.

После 7A одна core mapping responsibility не должна одновременно существовать
в старом application package и в `mapping/`.

7A завершён 2026-07-29. `dto.py`, `engine.py`, `rows.py`, `raw_tables.py`,
`drafts.py`, `control_totals.py`, `validation.py` и mapping-specific errors
теперь принадлежат canonical `mapping/`. Старые семь core-модулей удалены,
consumers переведены напрямую без facades. Draft actor переименован в
`StatementMappingDraftBuilder.build_rows(...)`.

Число production Python-файлов временно изменилось с 80 до 81, потому что
mapping errors отделены от всё ещё существующего root `errors.py` с
import-review ошибкой. Production Python уменьшился с 10 900 до 10 898 строк.
Это ожидаемый ownership change; сокращение packages и wrappers выполняется в
7B–7D. Полный regression gate после 7A: Ruff, ty и 602 tests.

#### 7B. Templates и persistence boundary

- собрать defaults, JSON codec, signatures и template operations в
  `mapping/templates.py`;
- удалить `template_use_case.py` как forwarding wrapper;
- repository оставляет у себя только SQLAlchemy queries и persistence;
- application/query actors не возвращают ORM template entities;
- отсутствие bank или statement type означает отсутствие matching templates,
  а не отдельный use case;
- сохранить workspace scope и точный template-signature contract.

Один `templates.py` предпочтительнее трёх маленьких модулей. Он разделяется
только если после переноса действительно содержит несколько устойчивых причин
изменения.

7B завершён 2026-07-29. Defaults, codec, signature matching и save operation
собраны в `mapping/templates.py`; пять старых template-модулей, включая
forwarding `template_use_case.py` и `values.py`, удалены. Reader получает
`MappingRepository` напрямую через узкий protocol.

Application и query actors работают с immutable `MappingTemplateSnapshot`.
`ImportMappingTemplate` теперь виден только persistence-моделям и
`mapping/repository.py`. Repository создаёт ORM entity из явных значений,
возвращает snapshot и не выполняет запрос без bank и statement type.
Одноразовые create/command DTO не добавлялись.

После 7B пакет `imports` уменьшился с 81 до 77 Python-файлов и с 10 898 до
10 892 строк production Python. Consolidated `templates.py` содержит 501 строку
после форматирования: это осознанная единая template capability без ORM и
workflow orchestration; повторное разделение допускается только при появлении
разных устойчивых причин изменения. Regression gate: Ruff, ty и 603 tests.

#### 7C. Commands и queries

- разделить текущий reader на overview, preview и source-row queries;
- preview не загружает templates через общий snapshot, если они ему не нужны;
- перенести изменяющий состояние workflow в
  `mapping/commands/import_rows.py`;
- результат import command возвращает DTO с document id/status, а не
  `UploadedDocument` ORM entity;
- общий workflow от mapped rows до сохранённых и проверенных raw transactions
  выразить actor API `MappedStatementRowImporter.import_rows(...)`;
- сохранить одну внешнюю транзакцию, idempotency fingerprint, replay и
  conflict behavior.

Целевые читаемые точки входа:

```text
StatementMappingOverviewReader.read(...)
StatementMappingPreviewReader.read(...)
StatementMappingSourceRowsReader.read(...)
StatementMappingImportService.import_rows_idempotently(...)
MappedStatementRowImporter.import_rows(...)
```

`Class.action` сохраняется намеренно. Не вводятся неопределённые `Manager`,
`Processor`, generic `UseCase` или свободные workflow-функции.

7C завершён 2026-07-29. Общий reader разделён на три независимых query actor:
overview, preview и source rows. Preview больше не загружает templates и не
принимает неиспользуемую default currency. Изменяющий состояние workflow
перенесён в `mapping/commands/import_rows.py`; command возвращает
`StatementMappingImportResult` с document id/status вместо ORM entity.

Оба пути импорта используют одного actor:
`MappedStatementRowImporter.replace_rows(...)` для manual mapping и
`MappedStatementRowImporter.import_rows(...)` для fallback. Булевый
переключатель поведения не используется. Внешняя транзакция, fingerprint,
idempotency replay и conflict contract сохранены. Старый
`application/unknown_statement_mappings/` удалён уже на этом шаге без facade и
compatibility imports.

После 7C пакет `imports` содержит 79 Python-файлов и 10 924 строки production
Python. Рост относительно 7B составляет два файла и 32 строки: один широкий
reader физически разделён на три query-модуля, добавлены явные узкие protocols
и result DTO. Это осознанная цена явных read/write boundaries; старый package
из четырёх файлов и 1 127 строк при этом удалён.

PostgreSQL characterization подтверждает, что два конкурентных запроса с одним
idempotency key создают одну execution record: первый выполняет импорт, второй
получает replay. Regression gate после 7C: Ruff, ty, 604 обычных tests и
отдельно прошедший PostgreSQL concurrency test.

#### 7D. Analysis consolidation и удаление старых путей

- перенести unknown-statement analysis в `mapping/analysis/`;
- объединить profiles, suggestions и value detectors в `columns.py`;
- объединить table detection, continuation и table construction в
  `tables.py`;
- объединить hints и control-total detection в `hints.py`;
- оставить самостоятельными `analyzer.py`, `text_tables.py` и analysis DTO;
- перенести fallback orchestration в `statements/process.py`;
- удалить оставшийся `application/unknown_statements/` после обновления всех
  consumers (`application/unknown_statement_mappings/` удалён в 7C);
- не оставлять пустые packages, aliases и compatibility imports.

7D завершён 2026-07-29. Analysis собран в canonical
`mapping/analysis/`: DTO, column evidence и suggestions, table
detection/continuations, text candidates, hints/control totals и главный actor
`StatementAnalyzer.analyze(...)`. Конфигурационный JSON перемещён рядом с
владеющим им `hints.py`.

Fallback orchestration теперь находится в `statements/process.py` и выражена
через `StatementMappingFallbackPipeline.apply_template_or_prepare_review(...)`.
Старый `application/` удалён целиком вместе с обоими unknown-statement
packages. Compatibility aliases, package facades и пустые директории не
оставлены.

После 7D весь `imports` содержит 72 Python-файла и 10 845 строк production
Python: на семь файлов и 79 строк меньше, чем после 7C. Сам `mapping/`
содержит 24 Python-файла — верхняя граница запланированного диапазона 22–24.
Regression gate после 7D: Ruff, ty, 604 обычных tests и отдельно прошедший
PostgreSQL concurrency test.

Этап 7 не вводит generic Unit of Work, event bus, plugin architecture или новый
repository abstraction. Существующие API-преобразования с реальной семантикой
— zero/one-based индексы, warning field names и control-total references —
остаются явными.

Критерии завершения этапа:

1. вся capability доступна через один root `imports/mapping`;
2. commands не возвращают ORM наружу, queries не выполняют mutations;
3. auto-template fallback и manual mapping создают одинаковые raw drafts;
4. workspace scope, idempotency и одна внешняя транзакция сохранены;
5. старые два application package удалены;
6. mapping preview/import, validation, template matching и source-row tests
   проходят;
7. перед изменением mutation boundary на 7C существует PostgreSQL gate для
   конкурентного mapping import/idempotency либо явно зафиксирована причина,
   почему он отложен.

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
- 10A: перевести document DTO/read projections на общий immutable Pydantic
  contract, удалить изоморфный API mapper и positional SQL row mapping;
- следующие capabilities переводить на Pydantic по одному законченному срезу,
  одновременно удаляя механические mappings и JSON codecs;
- пересмотреть оставшиеся маленькие helpers и названия;
- обновить module-level architecture documentation.

10A завершён 2026-07-29. Document DTO, snapshots, filters и read projections
переведены на общий immutable `ApplicationModel`. Изоморфный 199-строчный
document API mapper удалён; API вызывает response
`model_validate(...)` напрямую. List repository использует именованные
SQLAlchemy mappings вместо позиционной распаковки 15 колонок.

Change set уменьшил production Python на 236 строк. Формат `Decimal` в document
detail остаётся decimal string и теперь принадлежит serializer API-схемы.
Regression gate: Ruff, ty, 604 tests; один отдельный PostgreSQL concurrency test
пропущен без `BOOKER_TEE_TEST_DATABASE_URL`.

### Шаг 11. Parser normalization

- сохранить отдельный fixture contract для каждого банка;
- объединять только доказанно одинаковый parsed-fields → draft переход;
- не вводить plugin framework без нового реального extension scenario.

Текущий статус:

| Шаг | Статус |
|---|---|
| 0. Documentation consolidation | completed 2026-07-29 |
| Safety baseline | completed 2026-07-29: Ruff, ty, 601 tests |
| 1. Persistence ownership | completed 2026-07-29 |
| 2. Duplicate evidence | completed 2026-07-29 |
| 3A. Documents read side | completed 2026-07-29 |
| 3B. Documents lifecycle and persistence | completed 2026-07-29 |
| 3C. Documents commands and infrastructure | completed 2026-07-29 |
| 4. Statements | completed 2026-07-29 |
| 5A. Protocol, registry and extractors | completed 2026-07-29 |
| 5B. Parser support | completed 2026-07-29 |
| 5C. Bank parsers | completed 2026-07-29 |
| 5D. Old parsing package cleanup | completed 2026-07-29 |
| 6A. Stored report schema | completed 2026-07-29 |
| 6B. Decode once on documents read boundary | completed 2026-07-29 |
| 6C. Typed mapping consumers and decoder cleanup | completed 2026-07-29 |
| 7A. Mapping core ownership | completed 2026-07-29 |
| 7B. Mapping templates and persistence boundary | completed 2026-07-29 |
| 7C. Mapping commands and queries | completed 2026-07-29 |
| 7D. Mapping analysis consolidation and old-path cleanup | completed 2026-07-29 |
| 10A. Documents Pydantic models and mechanical mapping cleanup | completed 2026-07-29 |
| 8–9, 10B+, 11 | pending |

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
| 2026-07-29 | Review reads, locks, queue, status и links перенесены в `ImportReviewRepository` |
| 2026-07-29 | Pydantic принят стандартом application data; `dataclass` оставлен для runtime-композиции |

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
