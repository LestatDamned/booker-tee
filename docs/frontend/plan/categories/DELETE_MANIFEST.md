# Categories future delete manifest

Статус: `executed 2026-08-01`; delete gate пройден.

## Удалить полностью

- `src/app/features/categories/router.py`;
- `src/app/features/categories/presentation/`;
- `src/app/templates/categories/index.html`;
- `src/app/templates/categories/detail.html`.

## Удалить или переписать точечно

- import/include legacy Categories router из `src/app/main.py`;
- Categories presenter/router/template assertions из
  `tests/features/categories/test_categories.py`; domain/service tests остаются
  и при необходимости разделяются по ответственности;
- category template assertions из
  `tests/features/reference_data/test_reference_templates.py`; после cleanup
  других tests в файле не осталось, поэтому удалён весь файл;
- selectors `category-card*`, `category-list-feedback*`,
  `category-create-*`, `category-detail-*`, `category-form*`,
  `category-more-actions*` и category-only responsive group entries из
  `src/app/static/css/app.css`;
- `category-card--recent`, `.category-list-feedback` и `recent_category_id` из
  shared arrays `src/app/static/js/entity-target.js`; файл остаётся для Rules или
  другого named legacy consumer;
- legacy HTML/form `/categories*` operations из generated OpenAPI посредством
  штатной regeneration;
- category SSR preparation/selectors в `scripts/ui_audit.py`; realistic fixture
  создаёт category через JSON API/React flow.

## Изменить, а не удалить

- `frontend/app/routes.ts`: register directory/detail routes;
- `frontend/app/shell/app-shell.tsx`: отметить Categories как React route;
- `src/app/api/v1/router.py`: include JSON Categories router;
- Reports React `categoryDetailHref`: `/app/categories/:id` с filters/return;
- legacy `base.html`: Categories navigation ведёт на `/app/categories`;
- legacy Transaction Rules links назад в category — canonical React detail;
- `src/app/legacy_frontend_redirects.py`: query-preserving GET redirects для
  collection и UUID detail; legacy POST routes не сохранять;
- redirect, API, Reports route и UI audit tests;
- parent frontend plan completion record только после cleanup.

## Обязательно сохранить

- `models.py`, Category enums/table/FKs/indexes/relationships;
- repository/service либо их явно эволюционировавшие application/domain
  boundaries;
- system/default/property-workspace seeds and tests;
- Ledger/RawTransaction/TransactionRule category references;
- Manual Ledger, Import Review, Accounts, Reports, Transaction Rules и Chat
  consumers;
- migrations и сохраняемые domain/API integration tests;
- shared Reports summary policy;
- generic legacy CSS/JS/Jinja foundations, пока Transaction Rules или другой
  named runtime consumer ещё существует.

## Replacement test map

| Удаляемое наблюдение | Замена |
| --- | --- |
| presenter view/row/action policy | directory API DTO/capability + React projection tests |
| create/edit SSR draft preservation | React field/focus/draft + API validation tests |
| recent anchor/redirect | committed collection update + Toast/focus tests |
| SSR detail summary/operations/rules | detail reader/API financial invariant + React detail tests |
| safe Reports `return_to` presenter | route parser/open-redirect tests |
| archive/restore/delete rendering | API blocker/conflict tests + dialogs/retry tests |
| template read-only hiding | API capabilities + React read-only tests |
| legacy responsive cards/table | component tests + 1440/920/390 browser audit |

## Delete gate searches

```bash
rg -n "CategoryPagePresenter|categories/(index|detail)\.html|category-card|category-create|category-detail|recent_category_id" src tests frontend scripts
rg -n '"/categories"|/categories/|/categories\?' src tests frontend scripts
```

Допустимы compatibility redirects/tests, `/api/v1/categories` contracts,
canonical `/app/categories*`, domain model/repository/service references и
explicit temporary links to `/rules` until Transaction Rules cutover. Каждый
остальной result должен быть удалён или назван как runtime consumer.
