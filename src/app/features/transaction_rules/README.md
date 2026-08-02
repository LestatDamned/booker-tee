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
React -> /api/v1/transaction-rules adapter
-> application use cases
-> domain rules
-> repository.py
-> models.py
```

Versioned API router знает только про HTTP schemas, permissions и application
services. Historical browser `GET /rules` принадлежит общему compatibility
redirect layer и сохраняет query при переходе на `/app/rules`.

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

- `app.api.v1.transaction_rules` - versioned JSON read/write adapter.
- `application/commands.py` - write-side command dataclasses.
- `application/directory.py` - workspace-scoped paginated React read model.
- `application/mutations.py` - React/API mutation facade and committed DTOs.
- `application/rule_management.py` - create/update/toggle/delete and rule from raw confirmation.
- `application/target_resolution.py` - workspace and lifecycle validation for category,
  property and dormant account references.
- `application/rule_application.py` - apply active rules to raw transactions/documents.
- `application/fixture_seeding.py` - seed default merchant suggestion rules.
- `repository.py` - SQLAlchemy persistence and read queries.
- `models.py` - `TransactionRule` persistence model and rule enums.
- `errors.py` - transaction-rule-specific application exceptions.
- `domain/text.py` - rule text cleanup and generated names.
- `domain/matching.py` - pure matching predicates and raw transaction classifiers.
- `domain/suggestions.py` - suggestion payload application and cleanup.
- `domain/patterns.py` - rule pattern inference from raw descriptions.
- `domain/validation.py` - pure text and Decimal range validation for write commands.

## Hardened write contract

- Standalone commands own commit/rollback; Import Review uses the explicitly
  named `create_rule_in_transaction()` and keeps the outer transaction.
- Interactive create always creates the reviewed command and never silently
  returns a weak `pattern + category` match.
- Update/lifecycle/delete accept `updated_at` snapshots; mutation queries lock
  the workspace-scoped rule row.
- Create and changed targets must be active and belong to the rule workspace.
  Update may retain its current archived reference; enable revalidates all
  current targets.
- Delete requires a disabled rule with no direct raw suggestions. The database
  FK uses `RESTRICT`, so a concurrent reference cannot erase provenance.
- Default seeding locks the workspace, creates only missing rows and never
  mutates an existing user rule.
- Directory reads never seed or commit categories.

## Browser ownership

- canonical authenticated page: `/app/rules`;
- React Router path inside the SPA: `/rules`;
- historical `GET /rules?...` returns query-preserving `307`;
- no legacy form/HTMX mutation route remains;
- rules in Import Review and Categories use React navigation;
- the API/domain code remains the behavior owner for non-browser consumers such
  as Import Review, parsers/mapping and Chat.

## Import style

Prefer explicit imports from concrete modules over package-level re-export
barrels. For example, import matching predicates from `domain/matching.py`,
suggestion helpers from `domain/suggestions.py`, and command dataclasses from
`application/commands.py`.

The legacy SSR router, Jinja presenter/templates, Python list projection and
form-only tests were removed after the React replacement gate. This module is
intentionally cohesive; do not restore a second browser presentation stack.
