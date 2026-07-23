# Slice 05: Imports Cutover And Cleanup

Статус: planned.

## Outcome

React становится единственным Imports presentation stack. Все product entry
points ведут в него, historical GET URLs сохраняют совместимость redirects, а
legacy Jinja/HTML mutation surface удаляется.

## Canonical link migration

Проверить и обновить:

- React `AppShell`;
- Import Review back links, duplicate document links и rule actions;
- dashboard;
- reports;
- accounts list/detail;
- onboarding checklist;
- authenticated home;
- chat integration imports URL;
- workspace return paths;
- tests/fixtures и `scripts/ui_audit.py`.

Canonical targets:

```text
/app/imports
/app/imports/upload
/app/imports/documents/{document_id}
/app/imports/documents/{document_id}/mapping
/app/imports/documents/{document_id}/review
```

## Redirect policy

Оставить только GET compatibility redirects:

```text
/imports
/imports/upload
/imports/documents/{document_id}
/imports/documents/{document_id}/mapping
/imports/documents/{document_id}/review
```

Redirect сохраняет query string и hash-compatible target path. Historical HTML
POST endpoints upload/reparse/ignore/delete/mapping preview/import удаляются
после replacement gate; JSON API является единственной mutation surface.

Redirects размещаются в общем React adapter или узком compatibility router, а
не сохраняют feature presenters/templates.

## Consumer/delete verification

Выполнить consumer search для:

```text
src/app/features/imports/routes
src/app/features/imports/presentation
src/app/templates/imports
/imports
import-*
mapping-*
workflow-*
raw-transaction-*
Alpine/x-data
```

Удалить:

- legacy routes, presenters и templates из `INVENTORY.md`;
- Imports-specific legacy CSS;
- template/presentation tests без runtime consumer;
- legacy page scenarios/selectors из UI audit;
- obsolete generated OpenAPI HTML-route types.

Сохранить:

- application/domain/repository/models/parsers/storage;
- API review и React Import Review;
- business/application tests;
- compatibility redirects и их focused tests;
- shared legacy asset только при наличии конкретного оставшегося consumer.

## Replacement test manifest

Backend:

- полный `/api/v1/imports` contract suite;
- auth, workspace isolation и permission matrix;
- upload/reparse/failure/raw preservation;
- ignore/delete linked-operation restrictions;
- mapping preview/import/idempotency/deduplication;
- historical GET redirects и отсутствие legacy POST routes.

Frontend:

- format, lint, typecheck, unit/integration tests и production build;
- route loaders/actions and runtime schema parsing;
- deep links, Back/Forward и reload;
- error/stale/retry state;
- accessibility для forms, status, confirmation и focus.

Browser:

1. empty imports -> upload;
2. known statement -> detail -> review;
3. unknown statement -> detail -> mapping -> preview -> review;
4. parse failure -> detail -> reparse;
5. ignore/delete allowed and blocked cases;
6. viewer readonly flow;
7. canonical links из dashboard/accounts/reports/chat-shaped URL;
8. historical redirects;
9. desktop `1440×1000`, tablet `920×900`, mobile `390×844`;
10. no horizontal overflow, console/page/request errors.

Quality:

```text
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

Команды уточняются по фактическим scripts в `frontend/package.json`; нельзя
утверждать прохождение команды, которая не запускалась.

## Measurements

Перед Go записать отдельный measurements completion record:

- representative list/detail/mapping response raw+gzip size;
- bounded raw table/preview limits;
- query shape без роста на каждый document/raw row;
- upload/reparse local duration как engineering baseline, не production SLA;
- mapping initial DOM size и interaction timing на трёх viewport;
- список удалённых legacy строк/файлов как cleanup evidence.

## Final exit gate

- canonical navigation использует React;
- all imports JSON reads/mutations проходят через application boundary;
- financial/security policy не находится в browser authority;
- realistic flows и redirect tests прошли;
- legacy HTML mutation routes отсутствуют;
- legacy Imports templates/presenters/assets/tests удалены;
- consumer search не находит необъяснимый production legacy Imports UI;
- Stage 07 и child plan содержат completion record с реально выполненными
  checks, deviations, cleanup и measurements.
