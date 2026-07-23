# Stage 07 / Wave A: Import Documents And Mapping

Статус: planned.

Этот child stage мигрирует оставшийся пользовательский поток Imports после
завершения React Import Review:

```text
список документов
  -> загрузка
  -> карточка документа
  -> известная выписка -> существующий React review
  -> неизвестная выписка -> ручной mapping -> существующий React review
```

План не переписывает parsers, extraction, deduplication, document lifecycle,
mapping application use cases или ledger posting. Новый React frontend и
versioned JSON API становятся presentation adapters над существующим
application/domain кодом.

## Связанные документы

- [`INVENTORY.md`](INVENTORY.md) — наблюдаемое SSR-поведение, границы данных,
  security/invariants, geometry baseline и полный consumer/delete manifest.
- [`01_DOCUMENT_LIST.md`](01_DOCUMENT_LIST.md) — список документов и
  каноническая точка входа.
- [`02_UPLOAD.md`](02_UPLOAD.md) — загрузка и запуск обработки выписки.
- [`03_DOCUMENT_DETAIL.md`](03_DOCUMENT_DETAIL.md) — состояние документа,
  validation, parse history и management actions.
- [`04_MAPPING.md`](04_MAPPING.md) — ручной mapping неизвестной выписки,
  server preview и import.
- [`05_CUTOVER_AND_CLEANUP.md`](05_CUTOVER_AND_CLEANUP.md) — сквозной
  replacement gate, redirects и удаление legacy presentation.

## Почему это отдельный child stage

Workflow затрагивает четыре legacy-экрана, multipart upload, длительную
синхронную обработку, тяжёлые raw tables, destructive document actions и
сложную mapping-форму. Реализация достаточно велика, чтобы быть разделённой до
изменения production-кода, как требует Stage 07.

Оценка сложности: высокая, около `8/10`.

Ориентир для одного разработчика, включая API, React, проверки и cleanup:
`22–34` focused engineering days. Это planning range, а не срок или SLA.

## Порядок slices

| Порядок | План                                                     | Статус  | Пользовательский результат                                                |    Оценка |
| ------- | -------------------------------------------------------- | ------- | ------------------------------------------------------------------------- | --------: |
| 1       | [`01_DOCUMENT_LIST.md`](01_DOCUMENT_LIST.md)             | planned | Видит документы и открывает правильный следующий шаг                      |   2–3 дня |
| 2       | [`02_UPLOAD.md`](02_UPLOAD.md)                           | planned | Загружает PDF/XLSX и получает сохранённый результат обработки             |  3–5 дней |
| 3       | [`03_DOCUMENT_DETAIL.md`](03_DOCUMENT_DETAIL.md)         | planned | Понимает состояние документа и безопасно управляет им                     |  5–7 дней |
| 4       | [`04_MAPPING.md`](04_MAPPING.md)                         | planned | Настраивает неизвестную выписку через server preview и импортирует строки | 8–12 дней |
| 5       | [`05_CUTOVER_AND_CLEANUP.md`](05_CUTOVER_AND_CLEANUP.md) | planned | Использует только React Imports; legacy presentation удалён               |  3–5 дней |

Перед Slice 01 дополнительно закладывается `1–2` дня на typed API projections,
contract tests и уточнение idempotency upload. Это выполняется внутри первого
реального vertical slice, а не отдельным backend-only этапом.

## Канонические маршруты на время общей миграции

```text
/app/imports
/app/imports/upload
/app/imports/documents/:documentId
/app/imports/documents/:documentId/mapping
/app/imports/documents/:documentId/review
```

Исторические `/imports...` после replacement соответствующего экрана становятся
query-preserving compatibility redirects. Удаление `/app` prefix остаётся
отдельным общим routing cutover после миграции authenticated frontend.

## Общая API/state boundary

```text
React route
  -> generated/focused typed API client
  -> /api/v1/imports/*
  -> existing application query/use case
  -> workspace-scoped repository
```

Backend владеет:

- persisted document/row/parse statuses;
- workspace isolation и permission checks;
- возможностью review, mapping, reparse, ignore и delete;
- parser/mapping validation, warnings и preview;
- deduplication и созданием `RawTransaction`;
- document lifecycle и финансовыми ограничениями.

Frontend владеет:

- route navigation и query parameters;
- upload file selection;
- mapping draft и выбранной таблицей;
- disclosure/focus/confirmation state;
- форматированием, labels, tones и layout;
- retry UX, но не решением о допустимости повторной команды.

Server state не копируется в долгоживущий глобальный store. Начальная реализация
использует React Router loader/action и feature-local state. Новая cache/form
dependency требует отдельной доказанной проблемы и решения.

## Общие API-правила

- JSON DTO не используют ORM instances, legacy ViewModel или HTML fragments.
- API возвращает application facts и stable reason codes, а не CSS tones,
  русские labels или action URLs.
- Mutations возвращают smallest truthful committed snapshot, достаточный для
  согласованного UI.
- Reads не выполняют commit и не исправляют lifecycle побочным эффектом.
- Expected current status/version или другой явный stale-state guard
  проверяется для опасных повторных mutations.
- Upload и mapping import получают явную retry/idempotency policy до публикации
  mutation API.
- `storage_key` никогда не публикуется в browser DTO.
- Большие raw text/tables не входят в основной document response.

## Общие invariants

1. Все document, account, mapping template и raw-row lookups workspace-scoped.
2. Upload и management требуют import-management permission.
3. Parser и mapping import создают только reviewable `RawTransaction`, а не
   подтверждённые ledger records.
4. Повторная загрузка или повтор mutation не должны молча удваивать деньги.
5. Reparse запрещён при confirmed rows.
6. Ignore/delete запрещены при linked operations.
7. Неудачный parse сохраняет исходный документ и `ParseAttempt`.
8. Raw extracted data сохраняется на backend; браузер получает только
   необходимую и ограниченную projection.
9. React не вычисляет финансовую готовность, duplicate policy или lifecycle.
10. Existing React Import Review остаётся единственным consumer review workflow.

## Общий exit gate

Child stage завершён только когда:

- все четыре оставшихся экрана Imports работают через React и `/api/v1`;
- существующий Import Review остаётся совместимым конечным шагом;
- canonical navigation и все прямые product/chat links ведут в React;
- historical routes являются только query-preserving redirects;
- workspace isolation, permissions и destructive restrictions доказаны
  server tests;
- React tests покрывают route state, drafts, errors, accessibility и retries;
- realistic browser flow проходит на desktop, tablet и mobile;
- legacy routes, presenters, templates, selectors и replacement-only tests
  удалены;
- каждый оставшийся imports presentation файл имеет именованного runtime
  consumer;
- application/domain/parser/storage код не был переписан ради формы React.
