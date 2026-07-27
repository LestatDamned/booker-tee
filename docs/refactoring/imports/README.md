# Imports Refactoring

Статус: активный план.

Цель — разделить обработку выписок и import review, уменьшить связанность с
ledger и transaction rules, завершить React cutover и оставить тесты,
защищающие финансовые и data-integrity инварианты.

Рефакторинг не должен менять пользовательское поведение, API-контракты или
схему финансового учёта без отдельного решения.

## Документы

- [`FINDINGS.md`](FINDINGS.md) — подтверждённые больные места, риски и
  архитектурные границы.
- [`ROADMAP.md`](ROADMAP.md) — рекомендуемая целевая структура и этапы
  реализации маленькими commits.
- [`TEST_STRATEGY.md`](TEST_STRATEGY.md) — классификация текущих тестов и план
  сокращения стоимости поддержки.

## Главный вывод

`imports` сейчас содержит две разные продуктовые возможности:

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

Рекомендуется выделить `src/app/features/import_review` после удаления общего
reparse и дешёвой расчистки текущих границ. Парсеры, unknown-statement analysis
и mapping остаются внутри `imports`: это части одного statement-processing
workflow.

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
application orchestration known/unknown обработки принадлежит
`imports/application/statement_processing`.

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

## Definition of done

- общий пользовательский reparse отсутствует;
- statement processing не импортирует import-review application;
- ledger posting не обновляет imports/review lifecycle;
- React и chat используют один import-review application layer;
- `ImportRepository` и `ImportQueryRepository` разделены по устойчивым
  обязанностям;
- imports-specific SSR implementation отсутствует, compatibility redirects
  собраны в одном месте;
- тестовый набор организован по поведению и риску, а не по внутренним helper;
- README модулей описывают фактическую структуру.
