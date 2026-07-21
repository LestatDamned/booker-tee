# Slice 06: Confirm, Post и Consistency

Статус: planned.

## Результат

Writer подтверждает допустимый income/expense, при желании запоминает rule,
ровно один раз видит связанный ledger result и продолжает с очередного
достоверного queue item.

## Vertical scope

- Добавить action-specific confirm request с явной idempotency strategy.
- Повторно проверять capability и references внутри transaction; не доверять
  ранее загруженной React capability.
- Оставить posting, dedupe protection, rule creation/application, validation
  refresh и document lifecycle в одном atomic application workflow.
- Вернуть confirmed row/link, измененные rule sibling rows, queue, validation и
  document status, необходимые для немедленной reconciliation.
- Отображать stale/dedupe conflict как `409`, input/capability failures как
  стабильные `422` details, отсутствующие scoped entities как `404`.
- Поддержать undo posting только по существующим server lifecycle rules и с той
  же формой consistency response.

## Тесты

- enforcement category/property/workspace/confirmability;
- повторные confirm/import не могут double-count;
- rollback для remember-rule остается atomic, suggestions не auto-confirm;
- authoritative sibling/list/summary updates;
- retry, double submit, session expiry, readonly и network failure;
- imported income/expense корректно влияет на profit.

## Exit gate

Полный non-transfer confirmation path надежен без optimistic financial state и
не оставляет устаревших visible queue/validation consumers.
