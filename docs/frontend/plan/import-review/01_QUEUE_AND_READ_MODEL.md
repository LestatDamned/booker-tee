# Slice 01: Queue и типизированный Read Model

Статус: completed.

## Результат

Пользователь открывает review route документа в React, видит упорядоченные
исходные строки и точный progress queue, может перейти к первой оставшейся
строке и сравнить raw и normalized facts. В этом slice страница read-only;
legacy page остается production-путем для завершения review.

## Application и API

- Добавить минимальную queue policy и typed application read model из
  `INVENTORY.md`.
- Сделать read endpoint side-effect free и workspace-scoped.
- Открыть `GET /api/v1/import-review/{document_id}` с generated schemas.
- Использовать стабильный UUID и порядок `row_index`; не отдавать ORM или legacy
  `Review*VM` objects.
- Передавать read/write capability из membership, но пока без mutation actions.
- Считать `MATCHED` оставшимся/reviewable и защитить это regression test.

## React

- Добавить route `/app/imports/documents/:documentId/review` с client loader.
- Построить feature-local компоненты `ReviewQueue` и облегченный `ReviewItem` из
  generated types с runtime validation response.
- Сохранить deep link/focus первой оставшейся строки без глобального хранения
  server rows.
- Отобразить unauthenticated, forbidden/not-found, loading/error, empty, partial
  и complete states.
- Показывать raw source values, не отправляя приватные данные за пределы
  same-origin API.

## Тесты и проверки

- domain/application tests для terminal policy, counts и порядка;
- API contract/auth/workspace/readonly/no-side-effect tests;
- проверка актуальности generated schema и frontend runtime parsing tests;
- route/component tests для queue states и перехода к первой оставшейся строке;
- responsive/accessibility check на desktop, 920 px и mobile;
- focused legacy import-review tests остаются green.

## Exit gate

- Queue facts имеют одного server owner и не зависят от Presenter.
- React показывает realistic data через application -> API -> loader -> UI.
- UI не подразумевает financial mutation или ложную confirmability.
- Legacy review по-прежнему завершает workflow без изменений.

## Progress

Реализовано:

- единая domain queue policy с `MATCHED` как reviewable status;
- typed application reader без Presenter dependency и mutation на read;
- workspace-scoped `GET /api/v1/import-review/{document_id}`;
- generated TypeScript contract и runtime validation;
- React route, queue progress, stable anchors, raw/normalized source summary,
  readonly и request states;
- backend, API, component/route tests и production build.

Завершено browser gate:

- realistic scenario проверен на 1440×1000, 920×900 и 390×844;
- React route добавлен в общий Playwright UI audit для того же document UUID,
  который создается legacy upload/mapping flow;
- 51 page/viewport combination прошли без horizontal overflow, console/page/
  request errors и UX assertion failures.

Legacy route остается canonical для полного review workflow до Slice 07.
