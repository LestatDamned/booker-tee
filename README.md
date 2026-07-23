# Booker Tee

Booker Tee is a private financial assistant for turning bank statements and
manual money movements into trusted financial records, balances, and reports.

The original parser-first MVP has been completed and exceeded. The current focus
is to keep the financial core reliable while migrating the authenticated UI to
a maintainable React frontend and improving import-review workflows.

Core flow:

```text
PDF/XLSX/manual entry
  -> raw extracted data
  -> normalized draft rows
  -> validation and deduplication
  -> user review
  -> confirmed Operation + MoneyEntry
  -> balances and reports
```

Booker Tee is not full accounting software, ERP, tax filing, CRM, or an AI
finance platform. The product is deliberately centered on trustworthy financial
data, review-first workflows, workspace boundaries, and correct ledger posting.

## Current Capabilities

Implemented:

- Upload and preserve bank statement documents.
- Run parse attempts and preserve raw extracted data.
- Extract PDF tables/text with `pdfplumber`.
- Import unknown statement layouts through mapping templates.
- Normalize imported rows into reviewable raw transactions.
- Validate statement totals when available.
- Detect duplicates and support safe reparsing.
- Review, confirm, ignore, match, or mark imported rows as duplicate.
- Post confirmed rows into `Operation` + `MoneyEntry`.
- Keep internal transfers out of income, expense, profit, and property ROI.
- Manage workspaces, users, accounts, categories, properties, transaction rules,
  and manual operations.
- Show dashboard, account detail, import review, and report screens.
- Provide chat integration groundwork with strict workspace boundaries.

Current engineering focus:

- Build a versioned FastAPI JSON API without moving financial rules to the
  browser.
- Introduce the React foundation and migrate manual ledger as the first vertical
  pilot.
- Preserve the current UI geometry while moving to tokenized, theme-ready CSS.
- Use import review as the required complexity checkpoint before broad
  migration.
- Remove each superseded SSR presentation slice after its replacement passes
  tests and observation.

## Tech Stack

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0 async
- Alembic
- PostgreSQL
- TypeScript in strict mode
- React and React Router Framework Mode in SPA mode
- semantic CSS tokens, themes, and component CSS Modules
- FastAPI `/api/v1` JSON API
- Jinja2, HTMX, Alpine.js, and project CSS during legacy migration only
- `pdfplumber`
- uv, Ruff, ty, pytest

## Local Alpha Run

For a first local run, use the alpha scripts.

macOS or Linux:

```bash
./scripts/alpha-up.sh
```

Windows PowerShell:

```powershell
.\scripts\alpha-up.ps1
```

For a background smoke test:

```bash
./scripts/alpha-up.sh --detach
```

Windows PowerShell:

```powershell
.\scripts\alpha-up.ps1 --detach
```

If port `8000` is busy:

```bash
BOOKER_TEE_APP_PORT=8010 ./scripts/alpha-up.sh --detach
```

Windows PowerShell:

```powershell
$env:BOOKER_TEE_APP_PORT = "8010"; .\scripts\alpha-up.ps1 --detach
```

Open:

```text
http://127.0.0.1:8000
```

See [ALPHA_TESTING.md](docs/guides/ALPHA_TESTING.md) for the suggested tester
flow and feedback checklist.

Stop the local alpha:

```bash
./scripts/alpha-down.sh
```

Windows PowerShell:

```powershell
.\scripts\alpha-down.ps1
```

Reset local alpha data only when you want a clean start:

```bash
./scripts/alpha-reset.sh --yes
```

Windows PowerShell:

```powershell
.\scripts\alpha-reset.ps1 --yes
```

## Manual Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Start the application and PostgreSQL:

```bash
docker compose up --build
```

The app container runs migrations on startup through `docker/entrypoint.sh`.

## Local Debugging With VSCode

For debugger-driven development, run only PostgreSQL in Docker Compose and run
FastAPI on the host:

```bash
docker compose up -d postgres
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The `.env.example` file points `DATABASE_URL` at `localhost:5433`, the host port
exposed by `compose.yaml`.

In VSCode, use the `Booker Tee: FastAPI debug server` launch configuration. Keep
the Docker `app` service stopped while debugging locally so port `8000` is not
already in use.

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

Frontend commands will be added after the `frontend/` scaffold. The approved
package manager is npm with one committed `package-lock.json`.

Run UI audits:

```bash
uv run python scripts/ui_audit.py
uv run python scripts/ui_audit.py --scenario realistic
uv run python scripts/ui_audit.py --scenario review_interactions
uv run python scripts/ui_audit.py --scenario design_audit
uv run python scripts/ui_audit.py --scenario theme_audit --theme catppuccin-latte
```

## Server Runtime Settings

For a private server, do not run with local auth defaults. Set at least:

```bash
BOOKER_TEE_ENVIRONMENT=production
BOOKER_TEE_AUTH_SECRET_KEY=<strong random secret, 32+ chars>
BOOKER_TEE_SESSION_COOKIE_SECURE=true
BOOKER_TEE_ALLOWED_HOSTS=your-domain.example,127.0.0.1
```

In production mode the app refuses to start if the auth secret is still local,
session cookies are not secure, or allowed hosts are missing/wildcarded.

Chat integrations are disabled by default. When enabling Telegram/webhook mode,
set the matching `BOOKER_TEE_CHAT_INTEGRATIONS_ENABLED`,
`BOOKER_TEE_TELEGRAM_*`, and `BOOKER_TEE_PUBLIC_BASE_URL` values explicitly.

## Privacy Notes

Booker Tee handles sensitive financial data.

- Do not commit real bank statements, passports, contracts, `.env` files,
  tokens, passwords, or secrets.
- Local uploads are stored under `var/uploads/` and ignored by git.
- Local PDF fixtures under `tests/fixtures/` are ignored by git.
- Use sanitized fixtures for tests.
- Do not send financial documents to external services unless explicitly
  requested.

## Project Documents

The documentation index lives in [docs/README.md](docs/README.md). Start there
instead of reading every markdown file.

Main references:

- [AGENTS.md](AGENTS.md) - instructions for Codex and coding agents.
- [PROJECT_VISION.md](docs/product/PROJECT_VISION.md) - product compass.
- [ROADMAP.md](docs/product/ROADMAP.md) - planning reference.
- [DOMAIN_MODEL.md](docs/domain/DOMAIN_MODEL.md) - financial entities and
  invariants.
- [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) - code structure and
  feature boundaries.
- [Architecture decisions](docs/architecture/decisions/README.md) - accepted
  React runtime, API, CSS/theme, and learning decisions.
- [DESIGN.md](docs/design/DESIGN.md) - UI/UX principles and visual direction.
- [REACT_FRONTEND_DESIGN.md](docs/design/REACT_FRONTEND_DESIGN.md) - active
  React/API architecture, migration strategy, learning contract, and cleanup
  gates.
- [React implementation plan](docs/frontend/plan/README.md) - staged execution
  sequence with the current stage and exit gates.
- [FRONTEND_NEXT_DESIGN.md](docs/design/FRONTEND_NEXT_DESIGN.md) - superseded
  SSR strategy retained as a behavior reference.
- [WORKBENCH_ROW_DESIGN.md](docs/design/WORKBENCH_ROW_DESIGN.md) - historical
  detailed repeated-row UX specification.
- [REFACTOR_PROJECT_DESIGN.md](docs/design/REFACTOR_PROJECT_DESIGN.md) - legacy
  frontend behavior and implementation history.
- [MVP.md](docs/product/MVP.md) - historical parser-first MVP baseline and
  guardrails.
