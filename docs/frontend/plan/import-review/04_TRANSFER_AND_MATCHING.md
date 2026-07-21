# Slice 04: Transfer и Matching

Статус: completed.

## Реализовано

- `ImportReviewTransferReader` формирует typed accounts, raw-row candidates,
  existing manual transfer candidates и направление перевода. React не
  вычисляет eligibility, currency или баланс сумм.
- API принимает discriminated union из `new_transfer`, `raw_row_match` и
  `existing_operation_link`; лишние сочетания полей отклоняет Pydantic.
- Financial mutation требует `Idempotency-Key`. Новый и парный перевод хранят
  ключ и fingerprint на `Operation`; повторное связывание с тем же existing
  transfer распознаётся по persisted link.
- Source и paired raw rows блокируются в стабильном UUID-порядке, а выбранный
  manual transfer блокируется до повторной eligibility-проверки. Два
  конкурентных запроса не могут провести одну строку дважды.
- Committed response возвращает identifiers обеих строк, ids validation всех
  затронутых документов и полные review snapshots для current и paired
  document. React заменяет только current feature-local snapshot и не рисует
  confirmed state заранее.
- Stale или уже недоступный candidate возвращается как typed `409`; local
  selection при ошибке сохраняется.
- Legacy review route и его reviewer сохранены. Новый application service
  использует существующий `RawTransactionPoster`, не дублируя ledger rules.

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

Gate пройден: cross-document API test проверяет два возвращённых review,
application tests проверяют фильтрацию accounts/candidates и idempotent replay,
React test — reconciliation только после committed response.
