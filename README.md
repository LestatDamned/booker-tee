# Booker Tee

Booker Tee is a private financial assistant for turning bank statements and manual money movements into trusted financial records.

The project is currently an MVP. The first of three major product capabilities is implemented: reliable bank statement import into a reviewable ledger.

```text
PDF bank statement
  -> raw extracted data
  -> normalized transactions
  -> validation and review
  -> confirmed operations and money entries
  -> balances and simple reports
```

Booker Tee is not full accounting software, ERP, tax reporting, or an AI finance platform. The current goal is narrower: make imported financial data trustworthy before adding broader automation.

## Current Status

Implemented MVP capability:

- Upload PDF bank statements.
- Preserve uploaded documents and parser attempts.
- Extract raw PDF tables/text with `pdfplumber`.
- Normalize imported rows into raw transactions.
- Validate statement totals when available.
- Review, confirm, ignore, and repair imported rows.
- Post confirmed rows into `Operation` + `MoneyEntry`.
- Keep internal transfers out of income/expense/profit reports.
- Detect duplicate imports and support reparsing.
- Manage minimal accounts, categories, properties, transaction rules, and manual operations.
- Show useful account and report screens for monthly income/expense checks.

Planned later capabilities:

- More banks and configurable parser definitions.
- Deeper workspace collaboration, property workflows, and operational finance features.
- Automation, forecasting, and AI-assisted analysis after the core data pipeline is reliable.

## Tech Stack

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0 async
- Alembic
- PostgreSQL
- Jinja2 server-rendered templates
- HTMX/Alpine-ready UI
- Tailwind/CSS
- `pdfplumber`
- uv, Ruff, ty, pytest

## Local Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Start the application and PostgreSQL:

```bash
docker compose up --build
```

Open:

```text
http://127.0.0.1:8000
```

The app container runs migrations on startup through `docker/entrypoint.sh`.

## Development Commands

Install/sync dependencies:

```bash
uv sync
```

Run quality checks:

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

## Privacy Notes

Booker Tee handles sensitive financial data.

- Do not commit real bank statements, passports, contracts, `.env` files, tokens, passwords, or secrets.
- Local uploads are stored under `var/uploads/` and ignored by git.
- Local PDF fixtures under `tests/fixtures/` are ignored by git.
- If parser tests should run in a clean clone, add sanitized fixtures or make fixture-dependent tests skip when local files are missing.

## Project Documents

The main product and engineering references are:

- `PROJECT_VISION.md`
- `MVP.md`
- `ROADMAP.md`
- `DOMAIN_MODEL.md`
- `ARCHITECTURE.md`
- `AGENTS.md`

