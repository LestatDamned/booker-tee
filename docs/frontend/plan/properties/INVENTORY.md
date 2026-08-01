# Properties observed behavior inventory

Статус: audit snapshot для планирования; проверено по коду и тестам 2026-08-01.

## Текущий runtime flow

```text
GET /properties
  -> get_current_workspace_context
  -> PropertyService.list_all(workspace_id)
  -> PropertiesPagePresenter
  -> templates/properties/index.html

POST /properties | /properties/{id} | /archive | /restore
  -> CSRF + require_financial_write_context
  -> PropertyService
  -> workspace-scoped PropertyRepository
  -> commit
  -> 303 redirect или SSR form re-render
```

`src/app/main.py` регистрирует HTML router напрямую. В `/api/v1` Properties
router отсутствует; generated schema содержит только legacy HTML/form
operations для `/properties*`.

## Routes и authority

| Route | Поведение | Authority |
| --- | --- | --- |
| `GET /properties?recent_property_id=<uuid>` | все объекты workspace, recent banner и anchor | authenticated workspace context; explicit `can_read_workspace` dependency не используется |
| `POST /properties` | create active Property; 303 на recent row | financial write + CSRF |
| `POST /properties/{id}` | update name/short name/address; 303 на row anchor | financial write + CSRF + workspace lookup |
| `POST /properties/{id}/archive` | status=`archived`, устанавливает `archived_at` | financial write + CSRF + workspace lookup |
| `POST /properties/{id}/restore` | status=`active`, очищает `archived_at` | financial write + CSRF + workspace lookup |

SSR GET фактически доступен любому валидному участнику, а template скрывает
mutations через `workspace_permissions.can_write_financial_data`. Будущий API
должен использовать общий `get_api_request_context`, который уже явно требует
workspace read permission.

## Persistence и validation

`Property` содержит:

- `id`, `workspace_id`;
- required `name` (`String(255)`);
- optional `short_name` (`String(64)`) и `address` (`Text`);
- `status`, `created_at`, `updated_at`, `archived_at`;
- relationship к `Operation`.

Repository во всех entity lookup фильтрует `workspace_id`. `list_all` сортирует
по status/name, `list_active` возвращает только `active` и используется
справочниками других workflows.

Service нормализует whitespace, требует непустое name, превращает пустые
optional values в `None` и commit-ит каждую mutation. Ограничения 255/64 не
выражены в SSR controls или service validation, поэтому oversized input не
имеет хорошего field-error contract. Unique name отсутствует намеренно:
Reports группирует одинаковые названия по разным UUID; React не должен вводить
client-only uniqueness.

`updated_at` существует, но SSR mutations не передают expected value: два
редактора получают last-write-wins.

## Наблюдаемые пользовательские сценарии

1. Открыть единый список active/archived объектов.
2. Понять назначение объекта через hint и примеры.
3. Создать объект из раскрываемого блока; при ошибке сохранить введённые поля.
4. Получить recent-created banner и перейти к row anchor.
5. Раскрыть inline editor конкретной row и сохранить name/short name/address.
6. Архивировать active объект или восстановить archived объект.
7. Работать в read-only режиме без mutation controls.
8. Перейти из Properties в Reports.
9. Использовать active объекты как options в Manual Ledger, Import Review,
   Accounts correction, Transaction Rules и Chat review.

Пустой список автоматически открывает create accordion для writer; viewer
получает copy с просьбой обратиться к редактору.

## Финансовые и security invariants

1. Property — optional analytical reference, не денежный счёт и не источник
   баланса.
2. Property не меняет Operation type, `affects_profit` или MoneyEntry.
3. Transfer остаётся `affects_profit=false` и не попадает в property ROI.
4. Reports считает property totals только по confirmed profit operations и не
   смешивает currency.
5. Archive не удаляет Property, Operation или историческую связь.
6. Active picker не предлагает archived Property.
7. Все reads/mutations и reference resolution остаются workspace-scoped.
8. Browser получает capabilities/facts от server и не выводит permission или
   lifecycle policy из роли/status самостоятельно.
9. Hard delete отсутствует и не добавляется миграцией UI.
10. Mutation подтверждается только committed server snapshot; no optimistic
    financial/reference mutation.

## Важные фактические нюансы

- `PropertyStatus.INACTIVE` существует в model/migration, но ни один текущий
  writer его не устанавливает. Presenter считает inactive активным по tone и
  lifecycle action.
- `get_for_workspace()` проверяет ownership, но не active status. Archived
  property может оставаться целью существующего transaction rule и приниматься
  application resolver при explicit UUID.
- Archive не проверяет linked operations/rules и не каскадирует их lifecycle.
- В API нет stable Property error envelope, field errors, capabilities или
  concurrency conflict.
- В списке нет search/status filter/count/pagination; при росте workspace все
  rows рендерятся одним HTML response.

## Текущие тесты

### SSR-only observation tests

- `tests/features/properties/test_presentation.py` проверяет presenter state,
  anchors и redirect URLs;
- property-блоки в
  `tests/features/reference_data/test_reference_templates.py` проверяют create
  accordion, drawer edit, recent feedback и draft preservation.

Они фиксируют presentation для удаления, но не являются достаточной заменой
API/application tests.

### Сохраняемые domain/integration tests

- `tests/features/ledger/test_manual_operation_references.py` — active options
  и workspace-scoped references;
- `tests/features/reports/test_reports.py` — property profit summary и transfer
  exclusion;
- `tests/features/reports/test_reporting_overview.py` — filter/aggregate UUID,
  status и workspace query;
- `tests/api/test_reports_api.py` — property filter option/API boundary;
- Import Review, Accounts, Transaction Rules и Chat tests используют property
  references как часть своих contracts.

### Покрытие, которого сейчас нет

- прямые service/repository tests create/update/archive/restore;
- cross-workspace not-found tests для Property mutations;
- API auth/CSRF/permission/404/409/422 contracts;
- exact max-length/field-error behavior;
- concurrent edit/lifecycle conflict;
- explicit policy для inactive и archived rule target;
- React route/state/form/focus/responsive tests.

## Runtime consumers, которые нельзя удалить

| Consumer | Использование |
| --- | --- |
| Ledger models/mapping/application | `Operation.property_id`, relationship и posting resolution |
| Manual Ledger API/application | active reference list, filtering, create/edit |
| Import Review API/application | active references, draft evaluation/posting |
| Accounts API/React | imported operation correction и displayed property fact |
| Reports repository/API/React | filter options, property aggregates и exact UUID filters |
| Transaction Rules | target validation, suggestions и existing relationships |
| Chat integrations | short active choice list и confirmation state |
| Workspace model/migrations | ownership relationship и database integrity |

Поэтому `models.py`, `repository.py`, `service.py` и их domain consumers не
являются legacy presentation, даже если service будет аккуратно расширен для
API/concurrency.

