# Slice 06: Confirm, Post и Consistency

Статус: completed.

## Реализовано

- `ImportReviewConfirmationService` принимает typed income/expense command с
  обязательными `expectedStatus` и `Idempotency-Key`. Он повторно блокирует
  scoped row/document, проверяет references и domain confirmability и только
  затем вызывает существующий `RawTransactionPoster`.
- Sign суммы и выбранный income/expense теперь согласуются server-side через
  `operation_type_amount_mismatch`; React не может провести отрицательную сумму
  как доход или положительную как расход.
- Operation хранит idempotency key/fingerprint. Exact retry возвращает replay,
  reused key или stale/link state — typed `409`.
- Частичный unique index не позволяет двум конкурентным raw rows одного
  workspace стать `CONFIRMED` с одинаковым dedupe hash.
- Posting, optional rule creation, sibling rule application, повторный validation
  refresh, document lifecycle и commit остаются одной транзакцией. Ошибка rule
  откатывает созданные Operation и MoneyEntry.
- API возвращает authoritative review snapshots и operation identity. Read model
  содержит только posting facts (`operationId`, `canUndo`), без UI URLs/labels.
- React показывает confirm только после свежей server evaluation, не рисует
  financial success optimistically, сохраняет один idempotency key для retry,
  умеет запомнить rule и переводит focus к следующей строке после commit.
- Undo использует существующие server ledger rules, требует
  `expectedOperationId`, явное danger confirmation и возвращает тот же
  consistency envelope.
- Legacy confirm/undo routes сохранены до replacement gate Slice 07.

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

Gate пройден: application tests покрывают replay, stale/dedupe, server
confirmability и rollback rule; API/React tests — typed contracts, readonly,
authoritative reconciliation и undo confirmation. Production build и browser
audit на desktop/920/mobile прошли.

Completed: 2026-07-22

Implemented: atomic confirm command, idempotency/dedupe guards, versioned
confirm/undo API, React posting actions и authoritative read-model posting facts.

Checks run: full Python lint/type/tests, все frontend gates, production build,
Alembic head/offline SQL и UI audit.

Intentional deviations: response возвращает полный feature-local review snapshot
вместо row delta; это сохраняет уже доказанную consistency boundary без cache
library.

Cleanup performed: placeholder о будущем confirm удалён из React; legacy
workflow не удалялся.

Learning notes updated: feature README описывает idempotency и границу между
local draft и committed financial state.
