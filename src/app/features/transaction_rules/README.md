# Transaction rules module notes

`transaction_rules` отвечает за автоподбор смысла импортированной банковской
строки: категорию, объект, тип операции и режим применения правила.

Правило не должно незаметно и необратимо менять учет. Оно может предложить
значения или автоприменить безопасное совпадение, но пользователь должен иметь
понятный путь исправления.

## Product flow

```text
RawTransaction
-> active TransactionRule[]
-> rule match
-> suggestion fields on RawTransaction
-> review / ledger posting
```

## Target architecture

Внутри feature держим такой поток:

```text
router.py
-> application use cases
-> domain rules
-> repository.py
-> models.py
```

Router знает про формы, command builders, redirects и шаблон `/rules`. Он не
должен решать, как сравнивать rule pattern с банковским описанием.

Application use case описывает пользовательское действие: создать правило,
изменить правило, включить/выключить, удалить, применить правила к документу,
загрузить стартовые правила.

Domain rules чистые и тестируемые без БД:

- matching по workspace/account/direction/amount/text;
- нормализация имени, шаблона и описания;
- вывод direction и operation type из raw transaction;
- применение и очистка suggestion payload.

Внутренний код приложения обращается к конкретным use cases из `application/`,
а чистые правила - к `domain/`. Отдельный service facade сейчас не нужен:
модуль небольшой, а явные сценарии читаются лучше.

## Current module map

- `router.py` - HTTP endpoints and form-to-command builders for the rules page.
- `router_forms.py` - HTTP form parsing and command builders for the rules page.
- `application/commands.py` - write-side command dataclasses.
- `application/rule_management.py` - create/update/toggle/delete and rule from raw confirmation.
- `application/rule_application.py` - apply active rules to raw transactions/documents.
- `application/rule_queries.py` - read-side rule list query.
- `application/fixture_seeding.py` - seed default merchant suggestion rules.
- `repository.py` - SQLAlchemy persistence and read queries.
- `models.py` - `TransactionRule` persistence model and rule enums.
- `errors.py` - transaction-rule-specific application exceptions.
- `domain/text.py` - rule text cleanup and generated names.
- `domain/matching.py` - pure matching predicates and raw transaction classifiers.
- `domain/suggestions.py` - suggestion payload application and cleanup.
- `domain/patterns.py` - rule pattern inference from raw descriptions.

## Import style

Prefer explicit imports from concrete modules over package-level re-export
barrels. For example, import matching predicates from `domain/matching.py`,
suggestion helpers from `domain/suggestions.py`, and command dataclasses from
`application/commands.py`.

## Near-term cleanup plan

1. Keep pure domain rules outside `service.py`. Done.
2. Add command dataclasses for create/update forms. Done.
3. Split the old service facade into focused application use cases:
   `rule_management`, `rule_application`, and fixture/default seeding. Done.
4. Remove the unused service facade after callers move to concrete use cases.
   Done.
5. Add read-side DTOs only if the rules template starts depending on a rich ORM
   graph or display-specific computed fields.

This module is intentionally small. If a refactor makes rule behavior harder to
read, prefer the simpler shape.
