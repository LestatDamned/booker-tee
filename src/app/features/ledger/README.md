# Ledger runtime boundary

Ledger owns confirmed `Operation + MoneyEntry` persistence, manual workflows,
imported-operation corrections and posting policies.

- `application/` orchestrates workflows and owns transaction boundaries.
- `domain/` contains pure money, lifecycle and idempotency policies.
- `mapping/` builds semantic projections and persistence records.
- `schemas/` contains immutable application contracts.
- `repository.py` performs workspace-scoped aggregate queries.

Transfers are balanced, same-currency movements with `affects_profit=false`.
Lower-level writers never commit or roll back a caller-owned session. Import
parsers do not post ledger records.

General financial rules live in
[`docs/domain/DOMAIN_MODEL.md`](../../../../docs/domain/DOMAIN_MODEL.md).
