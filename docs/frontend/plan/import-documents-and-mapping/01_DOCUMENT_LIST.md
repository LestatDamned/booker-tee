# Slice 01: Document List

Статус: completed.

## Outcome

Пользователь открывает `/app/imports`, видит workspace-scoped документы,
понимает их состояние и переходит в detail, mapping или существующий React
review. Этот slice устанавливает typed documents API и новую каноническую точку
входа, не переписывая document application logic.

## API/application

Добавить read-only endpoint:

```text
GET /api/v1/imports/documents
```

Response содержит:

- workspace display context;
- page-level `canUpload` и readonly reason code;
- ordered document summaries;
- identity, filename, status, account reference и uploaded timestamp;
- bounded validation/row counts, необходимые списку;
- capabilities `canOpenDetail`, `canMap`, `canReview`;
- stable next-step kind, но не URL, button label или CSS tone.

Read должен быть side-effect free и не исправлять lifecycle через commit.
Status-to-capability policy должна находиться в application/domain boundary, а
не дублироваться в React.

## Frontend state/UI

- Route: `/app/imports`.
- Loader читает typed API response.
- Status filter вводится только если подтверждён существующим поведением или
  реальной потребностью; initial slice не изобретает новый list workflow.
- Empty, error, readonly и populated states обязательны.
- Primary action строится из typed next-step/capability.
- `AppShell` Imports link переключается на React только после replacement tests.

## Tests

Backend:

- workspace isolation;
- deterministic ordering;
- viewer/manager capabilities;
- status-to-next-step matrix;
- empty workspace;
- read не делает commit/mutation.

Frontend:

- loader/schema error;
- empty and populated rendering;
- accessible status text без зависимости только от цвета;
- правильные detail/mapping/review links;
- readonly state скрывает upload mutation, но не данные;
- responsive list/card geometry.

## Replacement/delete

После gate удалить:

- GET list branch из `routes/documents.py`;
- `ImportIndexPresenter` и list-only ViewModels;
- `templates/imports/index.html`;
- list-only template tests и CSS selectors.

Historical `GET /imports` становится query-preserving redirect на
`/app/imports`. Остальные legacy child pages пока остаются доступны по своим
URL до собственных gates.

## Exit gate

- canonical Imports navigation открывает React list;
- каждый status ведёт в правильный ещё живой React или legacy следующий шаг;
- list API workspace-scoped и side-effect free;
- old list template/presenter не имеют runtime consumers и удалены;
- browser list проходит desktop/tablet/mobile.

## Completion record

Завершено 2026-07-24.

- Добавлен read-only `GET /api/v1/imports/documents` с workspace-scoped
  projection, page/item capabilities и server-owned `nextStepKind`.
- Канонический экран `/app/imports` покрывает empty, error, readonly и
  populated states; AppShell использует React route.
- Historical `GET /imports` сохраняет query string и перенаправляет на
  `/app/imports`.
- Legacy list route, presenter/ViewModels, template, tests и list-only CSS
  удалены; upload, detail и mapping остаются до следующих slices.
- Backend: Ruff, ty и 561 pytest tests passed.
- Frontend: полный `npm run check`, 165 Vitest tests и production build passed.
- Browser audit `realistic --path imports`: desktop, tablet и mobile passed без
  overflow, console errors, page errors и failed requests.

### Масштабирование реестра

Уточнено 2026-07-24 после проверки сценария с большим числом выписок.

- Крупные document cards заменены компактным адаптивным реестром: таблицей на
  широком экране и короткими записями на мобильном.
- Основная идентичность выписки — счёт и период; банк даёт дополнительный
  контекст, а исходное имя файла остаётся вторичной технической меткой.
- Добавлены server-side пагинация, сортировка по времени загрузки и фильтры по
  пользовательскому состоянию, счёту и пересекающемуся периоду выписки.
- `maskedNumber` и `cardLast4` намеренно не входят в этот slice: их можно
  добавить позже отдельным продуктовым решением.
- Empty workspace и пустой результат фильтра различаются; фильтры и страница
  кодируются в URL и сохраняются при навигации.
