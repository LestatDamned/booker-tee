# Unknown Statement Importer

Статус: действующий contract fallback/mapping pipeline.

Unknown statement flow используется, когда known parser registry не распознал
PDF/XLSX. Он помогает пользователю сопоставить таблицу, но не проводит деньги.

## Pipeline

```text
extracted text/tables
  -> analyze unknown statement
  -> detect candidate transaction tables
  -> profile columns and rows
  -> suggest mapping/control totals
  -> auto-apply compatible workspace template OR require mapping
  -> server preview
  -> mapping import
  -> reviewable RawTransaction
  -> normal Import Review
```

Если PDF не дал table candidates, pipeline строит text-derived candidate
tables. Analysis сохраняется в validation report и raw tables текущего
`ParseAttempt`.

## Detected facts

Analyzer может определить:

- bank name и statement type;
- candidate tables и continuation tables;
- header/data row;
- date, description, amount, debit, credit, balance и currency columns;
- control totals;
- mapping suggestions, candidates, warnings и confidence.

Heuristics являются подсказкой, а не финансовой истиной.

## Mapping command

Поддерживаемые роли:

```text
operation_date
posting_date
description
amount
debit
credit
balance
currency
```

Также задаются:

- typed table identity: page number + table index;
- first data row;
- default currency;
- optional mapping template name.
- optional source-cell references for opening and closing statement balances.

Одна колонка не должна получать несовместимые роли. Должна существовать
достаточная комбинация date/description и amount либо debit/credit.

## Preview

Preview:

- выполняется server-side;
- не создаёт `RawTransaction`;
- использует тот же typed command, что import;
- возвращает normalized sample rows, warnings и row errors;
- должен быть bounded по числу строк и payload size;
- не раскрывает storage path или полный raw document без необходимости.

### Контрольные остатки

Mapping ищет однозначные строки «Входящий/Исходящий остаток» и близкие
варианты во всех raw tables. Автоматически применяется только один точный
кандидат для каждого вида остатка; неоднозначные варианты остаются на
подтверждение пользователя.

Пользователь может выбрать денежную ячейку вручную. Browser передаёт только
typed source coordinates `page/table/row/column`; server повторно читает raw
cell, разбирает `Decimal` и исключает всю выбранную строку из transaction
drafts. Исходная таблица не изменяется.

Выбранные значения и provenance сохраняются в `ParseAttempt.control_totals_json`.
Они участвуют в idempotency fingerprint и в preview reconciliation:

```text
opening balance + mapped row movement = calculated closing balance
calculated closing balance - statement closing balance = difference
```

Координаты контрольных строк не сохраняются в mapping template: расположение
остатков может меняться между выписками.

## Templates

`ImportMappingTemplate` принадлежит workspace и содержит bank/type signature,
default currency и column mapping.

Fallback может автоматически применить только совместимый template. Ошибка
auto-apply не теряет source: attempt остаётся `requires_review` с безопасным
validation message.

## Import

Mapping import:

- проверяет workspace document/account/template;
- создаёт только reviewable raw rows;
- запускает normalization, validation и deduplication;
- при повторном применении mapping заменяет только неподтверждённые старые rows;
- не создаёт confirmed operations;
- должен иметь idempotency/replay protection;
- после успеха ведёт в canonical React Import Review.

## Raw data and privacy

- Исходный file, raw text/tables и attempt сохраняются локально.
- Fixtures только sanitized.
- Raw content не логируется.
- Browser получает bounded projections.
- External AI/OCR service не используется без отдельного product decision.

## Current UI

React mapping workbench использует versioned API. Исходные строки загружаются
ограниченными окнами; preview и финансовая сверка остаются server-side.

## Tests

Обязательные cases:

- no table / text-derived table;
- single and multiple candidates;
- headerless/continuation tables;
- amount and debit/credit variants;
- duplicate column roles;
- invalid dates/amounts;
- template compatibility/auto-apply;
- preview has no persistence side effect;
- import preserves raw and deduplicates;
- workspace isolation.
