# Properties future delete manifest

Статус: execute только в Slice 05 после replacement gate.

## Удалить полностью

- `src/app/features/properties/router.py`;
- `src/app/features/properties/presentation/`;
- `src/app/templates/properties/index.html`;
- `tests/features/properties/test_presentation.py`.

## Удалить точечно

- import/include legacy Properties router из `src/app/main.py`;
- property template tests из
  `tests/features/reference_data/test_reference_templates.py` — сам файл
  остаётся для Categories/Transaction Rules legacy consumers;
- все property-only selectors из `src/app/static/css/app.css`:
  `property-card*`, `property-list-feedback*`, `property-create-details*`,
  `property-create-form*`, `property-form*`, включая их terms в shared mobile
  selector groups;
- `property-card--recent`, `.property-list-feedback` и
  `recent_property_id` из shared arrays в
  `src/app/static/js/entity-target.js` — файл остаётся до Categories/Rules
  cutover;
- legacy `/properties*` HTML operations и form-body schemas из generated
  OpenAPI TypeScript посредством штатной regeneration, не ручной правкой;
- SSR property preparation/selectors в `scripts/ui_audit.py`; realistic fixture
  должен создавать Property через versioned API/React flow.

## Изменить, а не удалить

- `frontend/app/shell/app-shell.tsx`: сделать Properties `reactRoute` и вести на
  SPA route;
- `src/app/templates/base.html`: legacy pages ведут на `/app/properties`;
- `src/app/legacy_frontend_redirects.py`: добавить query-preserving
  `GET /properties -> /app/properties`;
- `tests/core/test_legacy_frontend_redirects.py`: проверить query preservation и
  отсутствие legacy POST;
- `frontend/app/routes.ts`: зарегистрировать `properties` route;
- `src/app/api/v1/router.py`: зарегистрировать JSON Properties router;
- `scripts/ui_audit.py`: canonical authenticated page `/app/properties`, а
  `/properties` — redirect scenario;
- parent frontend plan: записать completion только после полного cleanup.

## Обязательно сохранить

- `src/app/features/properties/models.py` и database enum/table/relationships;
- `repository.py` и `service.py` либо их явно эволюционировавшие application
  boundaries;
- Property imports/relationships в Ledger, Workspace и Transaction Rules;
- Manual Ledger, Import Review, Accounts, Reports, Transaction Rules и Chat
  consumers active/reference behavior;
- migrations и сохраняемые domain/API tests, перечисленные в `INVENTORY.md`;
- shared `ActionVM`, legacy entity-card CSS/JS и Jinja base пока у них есть
  named Categories/Rules/public consumers.

## Replacement test map

| Удаляемое наблюдение | Замена |
| --- | --- |
| presenter row/status/action tests | application/API response + capability tests |
| template create/error preservation | React form interaction/focus/draft tests |
| anchor/recent banner redirects | authoritative collection update + Toast/row focus tests |
| SSR archive/restore redirects | API lifecycle 404/409/422 + React pending/retry tests |
| template read-only control hiding | API capabilities + React read-only rendering tests |
| legacy responsive card assertions | component tests + Playwright 1440/920/390 screenshots |

## Delete gate search

Перед merge Slice 05 consumer search не должен находить unexplained runtime
references:

```bash
rg -n "PropertiesPagePresenter|properties/index.html|property-card|property-create|recent_property_id" src tests frontend scripts
rg -n '"/properties"|/properties\?' src tests frontend scripts
```

Допустимы только compatibility redirect/tests и `/api/v1/properties` contracts.

