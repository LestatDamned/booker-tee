# Booker Tee commands

Запускайте команды из корня репозитория, кроме блоков с `cd frontend`.
Production-команды требуют явного `BOOKER_TEE_ENV_FILE`.

## Local alpha

```bash
./scripts/alpha-up.sh
./scripts/alpha-up.sh --detach
./scripts/alpha-down.sh
./scripts/alpha-reset.sh --yes  # удаляет только local alpha data
```

PowerShell использует соответствующие `.ps1` scripts.

## Host development

```bash
docker compose up -d postgres
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Backend checks

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
```

Ограничивайте pytest затронутым feature только для быстрой обратной связи;
перед release используйте полный gate. PostgreSQL race tests требуют
`BOOKER_TEE_TEST_DATABASE_URL`. Уровни тестов, правила сокращения и план
ускорения описаны в [`TESTING.md`](TESTING.md).

## Frontend

```bash
cd frontend
npm ci
npm run dev
npm run check
npm run api:generate  # только после намеренного API contract change
```

`npm run check` включает format, lint, styles, generated API contract,
typecheck, tests и production build.

## UI audit

```bash
uv run python scripts/ui_audit.py
uv run python scripts/ui_audit.py --scenario realistic
uv run python scripts/ui_audit.py --scenario review_interactions
uv run python scripts/ui_audit.py --scenario design_audit
uv run python scripts/ui_audit.py --scenario theme_audit --theme catppuccin-latte
```

Используйте только sanitized fixtures и не сохраняйте screenshots с private data.

## Production validation

```bash
export BOOKER_TEE_ENV_FILE=/absolute/path/production.env
chmod 600 "$BOOKER_TEE_ENV_FILE"
./scripts/production-preflight.sh
./scripts/release-gate.sh
```

Production Compose:

```bash
docker compose --project-name booker-tee-production \
  --env-file "$BOOKER_TEE_ENV_FILE" \
  -f compose.production.yaml config -q
```

Полный release/rollback порядок находится в
[`deploy/plan/README.md`](deploy/plan/README.md).

## Backup and restore rehearsal

```bash
BOOKER_TEE_ENV_FILE=/absolute/path/production.env \
  ./scripts/backup.sh /absolute/path/new-backup-directory

BOOKER_TEE_ENV_FILE=/absolute/path/production.env \
  ./scripts/restore-backup.sh /absolute/path/backup booker-tee-restore-test
```

Backup destination не должен существовать; restore работает только в новом
изолированном Compose project. Не выполняйте restore поверх production.
