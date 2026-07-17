# Manual Ledger Baseline

Статус: **working migration baseline**, Этап 1 первого пилота Frontend Next.

Дата фиксации: 14 июля 2026 года.

Этот документ описывает наблюдаемое поведение текущей страницы
`/ledger/manual`. Он нужен для реализации нового SSR web-adapter и не задает
его HTML, CSS, имена partials или ViewModel.

## 1. Scope и non-goals

В scope входят GET страницы, создание, lazy edit panel, изменение, отмена,
восстановление, удаление, фильтры, pagination, anchor/target, permissions,
workspace boundary, HTTP/HTMX responses, Alpine/JavaScript и доступный
responsive baseline.

В Этап 1 не входят:

- `src/app/web/`, Next templates и Next CSS foundation;
- изменение финансовой модели, application behavior или persistence;
- исправление найденных legacy-проблем;
- перенос current HTML/CSS и декоративных деталей;
- новая browser/E2E-инфраструктура.

## 2. Карта файлов и зависимостей

Основной поток:

```text
src/app/features/ledger/router.py
  -> LedgerPostingService
  -> ManualOperationUseCase / LedgerRepository
  -> LedgerViewMapper
  -> ManualOperationsPresenter
  -> src/app/templates/ledger/manual*.html
```

| Область | Текущие файлы | Ответственность |
| --- | --- | --- |
| HTTP | `src/app/features/ledger/router.py` | routes, form/query parsing, redirects, HTMX branch, template context |
| Application facade | `src/app/features/ledger/service.py` | list/get DTO и делегирование mutations use case |
| Workflow | `src/app/features/ledger/application/manual_operations.py` | create/update/cancel/restore/delete и транзакция |
| Commands/listing | `application/commands.py`, `application/listing.py` | mutation input, filters, pagination |
| Domain/factory | `domain/money.py`, `mapping/operation_factory.py` | signed amounts, transfer pairs, `affects_profit`, persistence construction |
| Queries | `src/app/features/ledger/repository.py` | workspace-scoped count/list/get и eager loading |
| Read mapping | `src/app/features/ledger/mapping/dto.py` | ORM -> immutable read DTO, entry direction и editable amount |
| Current presentation | `presentation/manual_operations/models.py`, `presenter.py` | row/edit VM, money tone, labels, actions, IDs и URLs |
| Templates | `templates/ledger/manual.html` и 5 partials в `templates/ledger/manual/` | page, create, filters, row, actions, lazy editor |
| Shared current presentation | `templates/base.html`, `templates/ui/_action.html`, `templating.py` | shell, action renderer, permissions/CSRF context |
| Current styles | `src/app/static/css/app.css` | shared form/row/drawer CSS и manual modifiers |
| Current behavior | `src/app/static/js/entity-target.js` | target/working/recent cleanup; manual использует target/working |
| Authorization | `workspaces/dependencies.py`, `workspaces/permissions.py` | current workspace context и write permission |
| Reference options | account/category/property services | workspace-scoped selects для create/edit/filter |

Router передает в current Jinja и подготовленный `manual_page_vm`, и старые
DTO/context values. Это переходный legacy-контракт; Next должен получать только
свои immutable ViewModel.

## 3. Маршруты и responses

| Method и URL | Permission | Обычный HTTP | HTMX/current contract |
| --- | --- | --- | --- |
| `GET /ledger/manual` | current workspace context | полная страница, `200` | отдельной ветки нет |
| `POST /ledger/manual` | financial writer | `303` на `?operation_id=<id>#operation-<id>` | такой же redirect; create не имеет локального response |
| `GET /ledger/manual/{id}/edit` | financial writer | HTML partial, `200` | `.manual-operation-edit-panel-content` загружается в drawer |
| `POST /ledger/manual/{id}` | financial writer | `303` на anchor операции | `_row.html`, `200`, target row заменяется через `outerHTML` |
| `POST /ledger/manual/{id}/cancel` | financial writer | `303` на anchor операции | новая row с status `ignored` |
| `POST /ledger/manual/{id}/restore` | financial writer | `303` на anchor операции | новая row с status `confirmed` |
| `POST /ledger/manual/{id}/delete` | financial writer | `303 /ledger/manual` | пустой response с `HX-Reswap: delete` |

`HX-Request` распознается только при точном значении `true`. Update/cancel/
restore используют row-local response. Фильтры и pagination работают обычным
GET. `operation_id` сохраняется в filter form и pagination URLs.

Текущая обработка ошибок:

- ошибки парсинга и `LedgerPostingError` становятся `400` с `detail`;
- одинаковый JSON/error response получают HTTP и HTMX;
- edit form, введенные значения и открытый drawer не восстанавливаются;
- целевые `422` validation и `409` conflict еще отсутствуют;
- optimistic concurrency/version еще отсутствует.

Это известный gap, а не продуктовый контракт для переноса.

## 4. Данные и финансовый смысл

Пользователь видит workspace, форму создания или readonly explanation,
фильтры, count/pagination и строки. Строка показывает дату, сумму, валюту,
description, category/property/account или transfer route, status и действия.

Сервер получает `OperationType` из `Operation.type`. Направление денег является
отдельным server-prepared значением `row.amount_direction`:

| `OperationType` | `amount_direction` | Entries и видимый смысл |
| --- | --- | --- |
| `income` | `income` | один положительный `MoneyEntry`; доход |
| `expense` | `expense` | один отрицательный `MoneyEntry`; расход |
| `transfer` | `transfer` | отрицательный source + положительный destination; маршрут счетов и «не влияет на прибыль» |

`LedgerViewMapper` получает transfer source/destination по знаку entries и
передает положительный editable amount. Presenter определяет тип, tone,
currency, тексты и действия. Jinja только выводит эти значения.

## 5. Состояния и действия

| Состояние | Видимый контракт | Writer actions |
| --- | --- | --- |
| `confirmed` | активная income/expense/transfer row | `исправить`, `отменить` |
| `ignored` | приглушенная row, status «игнор» | `восстановить`, destructive `удалить`; edit скрыт |
| readonly | данные и фильтры доступны; показано объяснение permissions | create/edit/lifecycle/delete скрыты |
| target | `operation_id` совпал с row на текущей странице | server class `--target`, URL hash прокручивает к anchor |
| working | пользователь взаимодействовал со строкой | global JS снимает target и добавляет `entity-card--working` |
| edit closed | только пустой drawer target с loading text | edit form не отрендерена заранее |
| edit open | partial со всеми reference options | save заменяет целую row и тем самым закрывает drawer |
| empty/no accounts | explanation + переход к accounts | create недоступен до появления account |
| empty/with accounts | объяснение назначения manual operations | create form остается главным действием |

Отдельного manual `recent` state нет. `draft` допускается use case при delete,
но current action policy не дает для draft lifecycle/delete action; обычный
manual create создает confirmed operation. Термина `archive` в этом workflow
нет: UI использует `cancel`, переводящий status в `ignored`.

Если targeted operation не попала под текущие filters/page, current backend ее
не pin-ит и не меняет pagination count: target просто отсутствует. Это не
соответствует принятому будущему pinned-target contract.

## 6. Anchor, drawer и client behavior

После create/update/cancel/restore fallback URL имеет форму:

```text
/ledger/manual?operation_id=<uuid>#operation-<uuid>
```

Browser выполняет anchor scroll. Presenter помечает совпавшую row как target.
При первом meaningful click или HTMX request `entity-target.js` удаляет hash и
`operation_id` через `history.replaceState`, очищает target/recent state и
делает взаимодействующую row working. После `htmx:afterSettle` working class
восстанавливается на замененной строке по тому же HTML ID.

Каждая row имеет Alpine scope `drawerOpen`. Edit button:

- переключает `drawerOpen` и `aria-expanded`;
- один раз загружает partial через `hx-trigger="click once"`;
- после загрузки сохраняет draft DOM при простом закрытии/открытии;
- не имеет отдельного действия «Отмена», сбрасывающего draft;
- после успешного save исчезает вместе со старой row.

Create и edit form имеют локальный Alpine `operationType`: destination account
показывается только для transfer, а скрытый select disabled. Финансовый смысл
в строке Alpine не вычисляет.

Global behavior: один `entity-target.js` (127 строк, 3.8 KB) с четырьмя
listeners (`click`, `htmx:beforeRequest`, `htmx:afterSettle`, `hashchange`).
Дополнительно создаются Alpine scopes: один create form, один на каждую row и
один внутри загруженного edit partial.

## 7. Workspace и финансовые инварианты

- Все list/count/get queries фильтруются по `workspace_id`; manual queries
  дополнительно фильтруются по `Operation.source == manual`.
- Account/category/property lookup получает только current workspace ID.
- Mutations требуют active owner/admin/editor через
  `require_financial_write_context`; viewer/uploader/analyst не пишут.
- Use case повторно загружает operation по `workspace_id + operation_id` и
  отвергает non-manual source.
- Income/expense создают один signed entry и влияют на profit по типу.
- Transfer создает равную пару entries в одной валюте и имеет
  `affects_profit=false`.
- Изменение типа полностью заменяет entries внутри транзакции.
- Cancel/restore меняют lifecycle status; ignored не влияет на официальный
  баланс. Confirmed operation нельзя hard-delete до cancel.
- Все mutation workflows commit/rollback целиком.

## 8. Current templates и CSS manifest

Feature templates, удаляемые после cutover:

```text
templates/ledger/manual.html
templates/ledger/manual/_create_form.html
templates/ledger/manual/_filters.html
templates/ledger/manual/_row.html
templates/ledger/manual/_row_actions.html
templates/ledger/manual/_edit_panel.html
```

Feature-specific current selectors: `.manual-operation-page`,
`.manual-operation-hero*`, `.manual-create-form`, `.manual-operation-row` и
modifiers `--income`, `--expense`, `--transfer`, `--target`, `--inactive`.
В current CSS обнаружено 11 уникальных `.manual-*` selectors.

Shared legacy dependencies нельзя удалить вместе с первым cutover, пока их
используют другие страницы: `.financial-row*`, `.row-drawer*`,
`.operation-form*`, `.filter-form*`, `.row-actions*`, `.ui-action*`, money
classes, `base.html`, `ui/_action.html` и `entity-target.js`.

## 9. Что сохраняем как продуктовый контракт

- дата, сумма и валюта всегда видимы; type и money direction готовит сервер;
- transfer показывает оба счета и не считается profit;
- description и понятная classification/status metadata;
- create/edit поддерживают income, expense и transfer;
- lazy edit loading без eager forms;
- writer/readonly action policy и workspace isolation;
- cancel before delete, restore ignored operation;
- row-local HTMX consistency после update/cancel/restore;
- обычный HTTP fallback с возвратом к понятной операции;
- stable row anchor, target return и working feedback;
- фильтры, pagination и empty/no-account explanations;
- keyboard-usable native forms/details, labels, radiogroup, `aria-controls`,
  `aria-expanded`, `aria-live` и отсутствие horizontal overflow.

## 10. Что не переносим

- блок «ID операции» и любой видимый UUID/debug payload;
- current CSS classes, wrappers, partial names и общий CSS cascade;
- передачу DTO/ORM-adjacent context параллельно с ViewModel;
- `400` JSON вместо локального `422` form response;
- отсутствие `409`/version и optimistic concurrency;
- target, который теряется из-за filters/pagination;
- отсутствие явной «Отмены» edit draft и детерминированного focus restore;
- глобальный current controller со знаниями о нескольких несвязанных feature;
- декоративную точность текущих borders, spacing и class order.

## 11. Существующие тесты

| Набор | Решение |
| --- | --- |
| financial/domain tests в `test_ledger.py` | сохранить и расширять только по финансовым причинам |
| workspace permission tests | сохранить |
| `test_manual_operations_presentation.py` | адаптировать к Next presenter; удалить current presenter checks после замены |
| `test_manual_operations_template.py` | заменить устойчивыми Next contracts; CSS/wrapper assertions удалить после cutover |
| новый `tests/ui_refactor/features/ledger/manual/test_manual_ledger_baseline.py` | сохранить до появления эквивалентного Next покрытия, затем адаптировать |

Baseline module фиксирует server-prepared financial meaning, GET + readonly
target, workspace propagation, lazy edit, HTTP redirect и HTMX row response.
Он намеренно не фиксирует full HTML snapshot, class order или текущий error
JSON.

## 12. Baseline-метрики

Метрики сняты без новой instrumentation:

| Метрика | Baseline |
| --- | --- |
| Основной production footprint | 19 файлов: 11 Python workflow/presentation, 6 Jinja, 1 CSS, 1 JS; shared auth/reference dependencies считаются отдельно |
| Python | 637 строк в feature-owned use case + current presenter/models; 2 084 строки при включении целиком shared router/service/repository/listing/mapping files |
| Jinja | 440 строк, 22 289 bytes в 6 manual templates |
| Current CSS | 7 578 строк, 160 314 bytes весь `app.css`; 11 уникальных `.manual-*` selectors; 42 уникальных shared row/drawer/form selectors |
| JavaScript | `entity-target.js`: 127 строк, 3 791 bytes, 4 global listeners |
| HTML, одна row | 16 864 bytes в детерминированном server render |
| HTML, 50 rows | 235 846 bytes в детерминированном server render |
| Eager edit forms | 0 в initial HTML для 50 rows; options загружаются lazy |
| List queries | типично 9 SQL round trips на прогретом workspace: 3 reference lists, count, operation select + 4 selectin loads; число не растет на row |
| Edit queries | типично 9 round trips: scoped operation + selectin relationships и 3 reference lists |
| N+1 | явного row-dependent N+1 нет; `selectinload` загружает category/property/entries/accounts пакетно |

Category default seeding может добавить queries и commit на первом посещении,
поэтому 9 — warmed-workspace baseline, а не универсальный предел.

Responsive current CSS имеет breakpoints `920`, `900`, `720`, `560`. На
`<=920px` row становится одноколоночной, action side переходит вниз, hero и
topline складываются; на mobile формы и фильтры становятся одноколоночными.
В `scripts/ui_audit.py` добавлен контрольный viewport `920x900` между desktop
`1440x1000` и mobile `390x844`.

Сценарий `realistic` дополнен существующим manual-ledger interaction check:
после create он повторно открывает target URL, подтверждает отсутствие eager
form, открывает lazy edit panel, проверяет переход target -> working и
horizontal overflow. Обычная закрытая row проверяется основным page audit.
Validation error и readonly остаются code/test baseline: current audit scenario
не умеет войти отдельным viewer, а current `400` error не является состоянием,
которое следует утверждать как успешный UI contract.

Финальный запуск проверил 45 page/viewport combinations и прошел. Для закрытой
и открытой manual row на каждом viewport получены `200`, нулевой horizontal
overflow и отсутствие console/page/request/UX assertion errors. Визуальный
просмотр screenshots подтвердил рабочую одноколоночную компоновку на `920px` и
mobile. Он также подтвердил legacy-шум: target делает filter accordion открытым
из-за учета `operation_id` как active filter, а UUID остается видимым рядом с
действиями. Оба решения не переносятся в Next.

## 13. Риски первого пилота

1. Validation lifecycle придется спроектировать заново: current contract не
   сохраняет форму и не различает `422`/`409`.
2. В модели нет integer `version`; optimistic concurrency затронет общий
   backend и требует отдельного согласованного этапа.
3. Pinned target и pagination consistency отсутствуют.
4. Текущий presenter смешивает URLs/action policy/formatting, а router передает
   двойной presentation context; копировать эту форму нельзя.
5. Lazy edit endpoint повторно загружает все reference lists; большие списки
   потребуют проверки, но преждевременная search-инфраструктура не нужна.
6. Current global target JS связан сразу с несколькими feature.
7. Full UI audit зависит от PostgreSQL, Playwright/Chromium и возможности
   запустить приложение; недоступность инфраструктуры должна быть явно указана.

## 14. Definition of Done для перехода к Этапу 2

- [x] Наблюдаемый current workflow и cleanup manifest зафиксированы.
- [x] Устойчивые baseline-тесты находятся в `tests/ui_refactor/`.
- [x] Query/HTML/CSS/JS и eager-form baseline снят.
- [x] В существующий UI audit добавлен viewport `920px`.
- [x] Focused, existing ledger, Ruff, ty и `git diff --check` успешно выполнены.
- [x] `realistic` UI audit выполнен на desktop, 920px и mobile.
- [x] Результат Baseline передан владельцу проекта на проверку.

Baseline принят владельцем проекта 17 июля 2026 года. После явной команды
владельца начат Этап 2; его текущее состояние зафиксировано в
[`FRONTEND_NEXT_DESIGN.md`](FRONTEND_NEXT_DESIGN.md).
