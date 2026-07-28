# Imports Refactoring

Статус: активный план.

Цель — завершить уже выполненное разделение обработки выписок и Import Review,
сократить навигационную стоимость и механический код, а затем укрепить
deduplication без потери финансовых и data-integrity инвариантов.

Рефакторинг не должен менять пользовательское поведение, API-контракты или
схему финансового учёта без отдельного решения.

## Документы

- [`FINDINGS.md`](FINDINGS.md) — подтверждённые больные места, риски и
  архитектурные границы.
- [`ROADMAP.md`](ROADMAP.md) — рекомендуемая целевая структура и этапы
  реализации маленькими commits.
- [`PHASE_6_IMPORT_REVIEW.md`](PHASE_6_IMPORT_REVIEW.md) — завершённый план
  выделения `import_review`, включая границы, транзакции, React/chat migration
  и удаление обратной зависимости ledger. Он остаётся историей принятого
  решения до финального сворачивания refactoring docs.
- [`TEST_STRATEGY.md`](TEST_STRATEGY.md) — классификация текущих тестов и план
  сокращения стоимости поддержки.

## Текущее состояние

Две продуктовые возможности уже разделены:

```text
imports
  -> сохраняет документ
  -> извлекает исходные данные
  -> создаёт reviewable RawTransaction

import_review
  -> классифицирует строку
  -> применяет пользовательское решение
  -> создаёт или связывает ledger operation
  -> выполняет transfer / confirmation / undo
```

`src/app/features/import_review` существует и является владельцем review
policies, read model и mutation actors. React и chat используют общие actors;
ledger posting принимает готовые финансовые facts и не меняет import lifecycle.

Оставшаяся работа начинается не с нового feature move, а с четырёх более узких
проблем:

1. убрать dead code, incidental imports и test-driven defensive branches;
2. оставить один typed validation reason/report boundary;
3. отделить duplicate evidence от `normalization_error`;
4. закончить ownership review persistence и сократить механические JSON/API
   mappings.

## Порядок продолжения

```text
Wave A  cheap cleanup
  -> dead wrappers
  -> defining-module imports
  -> строгие ImportReviewReader collaborators

Wave B  validation boundary
  -> один reason resolver
  -> один decoder persisted validation

Wave C  deduplication behavior
  -> overlapping statements characterization
  -> duplicate signal отдельно от normalization error
  -> PostgreSQL race guards

Wave D  persistence ownership
  -> document/mapping queries остаются в imports
  -> review rows/locks/linking/queue принадлежат import_review

Wave E  mechanical code reduction
  -> typed unknown-analysis JSON boundary
  -> Pydantic mapping для изоморфных API DTO

Wave F  tests and docs
  -> tests по фактическому feature owner
  -> удалить завершённый migration log

Wave G  parser normalization
  -> только после characterization всех bank parsers
```

Behavioral deduplication fix не объединяется с file moves или массовым
переименованием.

## Словарь границ

```text
documents
  -> загрузка, хранение и управление документом

statement_processing
  -> превращение извлечённого содержимого выписки в RawTransaction

mapping
  -> ручное описание колонок неизвестной выписки

import_review
  -> пользовательская проверка и проведение в ledger
```

Infrastructure extraction остаётся в `imports/infrastructure/extraction`, а
application orchestration known/unknown обработки принадлежит `imports`.
Физический move текущих cohesive файлов в `statement_processing/` выполняется
только если он уменьшает навигацию, а не ради симметрии target tree.

Общий пользовательский reparse удалён как неподтверждённый будущий сценарий.
Если позже появятся версии parsers или реальная потребность повторно
обрабатывать сохранённые документы, reprocessing проектируется отдельно по
фактическим требованиям.

## Неподвижные инварианты

1. Raw document, extraction payload, parse attempt и raw rows не теряются.
2. Parser и mapping никогда не создают confirmed ledger records напрямую.
3. Workspace остаётся обязательной границей каждого запроса.
4. Повторный upload, mapping или confirmation не должен удваивать деньги.
5. Transfer не влияет на income, expense, profit или property ROI.
6. Confirmed records не удаляются обычным document cleanup.
7. React API не раскрывает `storage_key`, SHA, полный raw text или raw tables.

## Целевая граница

```text
Imports API
  -> documents / mapping application
  -> imports repositories, domain, parsing and infrastructure

Import Review API / chat
  -> import_review application actors
  -> ImportReviewRepository
  -> LedgerPostingService / transaction rules
  -> imports document-validation/status collaborators
```

Правила направления:

- `imports` не импортирует `import_review`;
- ledger mutation не импортирует review application и не меняет raw rows;
- `import_review` оркестрирует review mutation и передаёт ledger только
  финансовые facts;
- persistence projections не импортируют application DTO;
- parser/support импортирует domain values из defining modules, а не через ORM.

## Definition of done

- общий пользовательский reparse отсутствует;
- statement processing не импортирует import-review application;
- ledger posting не обновляет imports/review lifecycle;
- React и chat используют один import-review application layer;
- duplicate evidence не хранится как normalization error;
- validation reason вычисляется одним policy;
- review persistence принадлежит `ImportReviewRepository`, document и mapping
  persistence не дробятся по ORM-моделям;
- imports-specific SSR implementation отсутствует, compatibility redirects
  собраны в одном месте;
- тестовый набор организован по поведению и риску, а не по внутренним helper;
- README модулей описывают фактическую структуру;
- завершённые migration phases удалены из active docs после переноса
  долгоживущих решений в module/architecture documentation.
