# Operations workspace

Статус: действующий product/API contract.

`Операции` — единый пользовательский поток confirmed денежных событий.
Manual, import, debt и system workflows создают одну persistence entity
`Operation`; `source` сохраняет provenance и допустимые действия.

```text
Operation
  type: income | expense | transfer | adjustment
  source: manual | bank_pdf | debt | system
  status
  1 -> N MoneyEntry
```

Raw import rows до подтверждения принадлежат Import Review. Ignored, duplicate и
неподтверждённые rows не становятся официальными операциями.

## Read и mutation boundary

```text
OperationsReader             all workspace operations
ManualOperationService       manual creation and correction
ImportedOperationCorrection  allowed import corrections
DebtService                  debt and compound payments
System policy                read-only without an explicit command
```

Универсальный `update_operation()`, обходящий source-specific validation, не
допускается.

Canonical route: `/app/operations`; selected operation хранится в
`operation_id` query parameter. Исторический `/app/ledger/manual` является
query-preserving redirect.

## Collection contract

По умолчанию показываются confirmed operations. Фильтры: type, source, status,
period, account, category, property и text query. Выбранная запись доступна по
deep link даже вне текущей страницы результатов.

Строка показывает дату, description, signed amount, account/transfer route,
source, category/property и только значимые statuses. Source — вторичный
provenance label, а не отдельный верхнеуровневый раздел.

## Actions

API возвращает capabilities и conflict errors. Manual operation может иметь
edit/cancel/restore/delete согласно version и ledger policy. Import, debt и
system sources ведут в owning workflow или поддерживают только явно разрешённую
correction. React не выводит эти права самостоятельно.

Каждый read/write workspace-scoped; transfer не влияет на profit; optimistic
version и idempotency защищают concurrent/repeated mutations.

Общие финансовые правила находятся в
[`docs/domain/DOMAIN_MODEL.md`](../../domain/DOMAIN_MODEL.md).
