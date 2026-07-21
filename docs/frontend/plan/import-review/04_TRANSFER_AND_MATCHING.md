# Slice 04: Transfer и Matching

Статус: planned.

## Результат

Writer классифицирует строку как transfer, выбирает другой account, связывает
парную противоположную raw row или подходящий existing manual transfer и видит
обновление всех затронутых consumers.

## Vertical scope

- Отдать typed transfer candidates без legacy panel VM или display labels.
- Оставить candidate eligibility, direction, account/currency equality и
  balanced amounts на server.
- Использовать discriminated request: new transfer, raw-row match или
  existing-operation link. Невозможные combinations должны быть невыразимы в
  API schema.
- Одним committed result вернуть current row, paired row (возможно, из другого
  document), queue/document summaries и identifiers обновленного validation.
- После success согласовать feature-local server state; не показывать confirmed
  transfer optimistically.
- Сохранять panel draft, а stale/ineligible candidates объяснять через `409` или
  `422` по смыслу.

## Тесты

- разные accounts, одинаковая currency, противоположные balanced amounts;
- workspace/status freshness candidate и eligibility existing transfer;
- transfer никогда не влияет на profit;
- paired rows связываются один раз, оба visible consumer обновляются;
- retry/double-submit/idempotency audit и cross-document consistency.

## Exit gate

Smallest truthful consistency response доказан без HTMX OOB equivalent или новой
cache library.
