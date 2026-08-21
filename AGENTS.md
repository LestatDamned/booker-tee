# Booker Tee agent instructions

Booker Tee is a private financial assistant for reliable import, review and
ledger workflows. Prefer small changes that preserve financial correctness.

## Read first

1. This file.
2. [`docs/README.md`](docs/README.md).
3. One task-specific document named there.
4. Relevant code and tests; they are the final behavior reference.

Do not load the whole documentation tree for one task.

## Stack and commands

Use the existing Python 3.12+, FastAPI, SQLAlchemy async, PostgreSQL, Pydantic
v2, React, TypeScript strict, React Router SPA, CSS Modules and semantic tokens.
Do not introduce another frontend/backend, queue, storage or AI stack without
explicit approval.

```bash
uv sync
uv add <package>
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
cd frontend && npm ci && npm run check
```

Use npm only in `frontend/`; keep the committed `package-lock.json`.

## Architecture

Default flow:

```text
React -> /api/v1 -> application service/use case -> repository -> model
```

- React is the only browser frontend. Do not restore Jinja/HTMX/Alpine.
- Routers own HTTP schemas, dependencies and responses, not workflows.
- Application code owns orchestration and transactions.
- Domain code owns pure financial and lifecycle policy.
- Repositories contain workspace-scoped database queries.
- Models define persistence; infrastructure handles files and providers.
- Prefer explicit imports and existing domain-specific actors.
- Add abstractions only after a repeated stable responsibility exists.

Backend owns financial state, authorization, action capabilities and validation.
React renders server contracts and does not infer these rules from raw fields.

## Non-negotiable invariants

- Every workspace-owned lookup is scoped by `workspace_id` or a validated
  workspace-owned parent. Never trust a client workspace id without membership.
- Use `Decimal`/PostgreSQL `Numeric`, never `float`, for money.
- Confirmed `Operation -> MoneyEntry` records determine balances and reports.
- Transfers are balanced and have `affects_profit=false`.
- Draft, review, ignored and duplicate records do not affect official balances.
- Parsers and mapping never create confirmed ledger records directly.
- Preserve uploaded documents, parse attempts and raw extracted rows on failure.
- Upload, mapping, confirmation and retry must not double-count money.
- Correct confirmed records carefully; do not casually hard-delete them.
- Tenant security deposits are not income until retained.

## Security and persistence

- Do not commit or log real statements, raw financial payloads, account numbers,
  secrets, tokens, passwords or `.env` files. Use sanitized fixtures.
- External AI/API processing of private financial data requires explicit approval.
- Use Alembic for schema changes, deterministic migrations, ownership foreign
  keys and indexes for common workspace-scoped queries.
- Financial mutations must have one visible transaction owner and safe retry
  behavior. Do not hide commit/rollback inside lower-level helpers.

## Scope

Do not expand Booker Tee into ERP, CRM, tax software, asset management, SaaS
billing, broad AI/RAG or a second app unless explicitly requested. Chat remains
a narrow integration over the same workspace-scoped use cases.

## Finish

Run checks proportional to the changed risk. Prioritize transfer/profit,
workspace isolation, import preservation, deduplication, API/auth contracts and
React state tests. Report what changed, files touched, commands run, results and
anything not verified. Never claim a check passed if it was not run.
