# Booker Tee React Frontend

Новый frontend — отдельный presentation adapter к FastAPI. Он работает под
`/app`, загружает compiled assets из `/assets`, получает данные только из
`/api/v1/*` и не содержит финансовых правил.

## Требования

- Node.js 22.22 или новее;
- npm из поставки Node;
- запущенный FastAPI на `http://127.0.0.1:8000`.

Версию Node проверяет `engines` в `package.json`, а точные версии packages
фиксирует committed `package-lock.json`.

## Первый запуск

Из `frontend/`:

```bash
npm ci
npm run dev
```

Открыть `http://127.0.0.1:5173/app`. Vite проксирует `/api`, `/login` и `/logout`
в FastAPI, поэтому session cookie остаётся same-origin с точки зрения browser.

Если на host пока нет Node 22, тот же frontend запускается контейнером из корня:

```bash
docker compose --profile frontend up app frontend
```

## Команды качества

```bash
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run build
```

`npm run check` запускает их последовательно. Это frontend-аналог набора
`ruff + ty + pytest`, но каждая команда проверяет свой слой.

## Генерация API types

После изменения FastAPI schema из `frontend/` выполнить:

```bash
npm run api:generate
```

Команда экспортирует OpenAPI через Python app и обновляет
`app/api/generated/schema.ts`. Файл generated: его не редактируют вручную.
Если Node используется только через Docker, эквивалент из корня:

```bash
uv run python scripts/export_openapi.py frontend/openapi.json
docker compose run --rm --no-deps frontend npm run api:types
```

## Первый end-to-end flow

1. FastAPI `/api/v1/session` проверяет HttpOnly session cookie и workspace.
2. Pydantic сериализует JSON в camelCase; unsafe API дополнительно требует
   `X-CSRF-Token`.
3. OpenAPI generator создаёт compile-time `SessionDto`.
4. `sessionSchema` проверяет реально пришедший `unknown` JSON во время работы.
5. `loadSession()` превращает HTTP result в одно из явных состояний.
6. `SessionPage` загружает состояние только в browser, а `SessionShell` является
   обычной функцией отображения state в UI.

Подробнее: [`docs/typescript-for-python.md`](docs/typescript-for-python.md).
