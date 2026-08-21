# Booker Tee

Booker Tee turns bank statements and manual money movements into trusted
financial records, balances and reports.

```text
PDF/XLSX/manual entry
  -> preserved source and raw data
  -> normalized draft rows
  -> validation and deduplication
  -> user review
  -> confirmed Operation + MoneyEntry
  -> balances and reports
```

The product favors reliability, explicit review, workspace isolation and
correct ledger posting over silent automation. It is not ERP, CRM, tax software
or an AI finance platform.

## Stack

- Python 3.12+, FastAPI, SQLAlchemy async, Alembic, PostgreSQL and Pydantic v2;
- React, TypeScript strict and React Router SPA in `frontend/`;
- versioned same-origin FastAPI JSON API under `/api/v1`;
- semantic CSS tokens, themes and component CSS Modules;
- local PDF/XLSX extraction with `pdfplumber`;
- uv, Ruff, ty, pytest, npm, ESLint, Vitest and Playwright.

React is the only browser frontend. Historical GET routes may redirect to
`/app/*`; the Jinja/HTMX/Alpine presentation stack has been removed.

## Local alpha

```bash
./scripts/alpha-up.sh
# or: .\scripts\alpha-up.ps1
```

Open `http://127.0.0.1:8000`. Stop with `./scripts/alpha-down.sh`. Use
`./scripts/alpha-reset.sh --yes` only when local alpha data may be deleted.

See [`docs/guides/ALPHA_TESTING.md`](docs/guides/ALPHA_TESTING.md) for the smoke
flow.

## Development

```bash
uv sync
uv run alembic upgrade head
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
cd frontend && npm ci && npm run check
```

For host debugging, start PostgreSQL with `docker compose up -d postgres` and
run `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`.

Production must set a strong auth secret, secure session cookies, explicit
allowed hosts and the intended registration mode. Operational commands and
release steps are in [`docs/COMMANDS.md`](docs/COMMANDS.md) and
[`docs/deploy/plan/README.md`](docs/deploy/plan/README.md).

## Documentation

Start at [`docs/README.md`](docs/README.md). The code and tests remain the final
behavior reference.

Never use real private documents as fixtures or send financial data to external
services without an explicit decision.
