# REFACTOR_PROJECT_DESIGN.md — Frontend Refactor Anchor

Живой документ для подготовки и проведения рефакторинга frontend/SSR слоя Booker Tee.

```text
Status: active refactor anchor and implementation log
Read when: working on SSR frontend refactor, financial rows, actions, forms, imports, account detail, manual operations, or reports
Do not use as: general product roadmap
```

Цель документа: собрать решения до начала больших правок, чтобы рефакторинг был
последовательным, проверяемым и не превращался в серию случайных переделок.

## Как читать этот документ

Этот документ больше не является только планом первого import review slice. Он
теперь выполняет две роли:

1. фиксирует архитектурные решения, которые уже доказали себя в коде;
2. держит ближайший план frontend/SSR refactor, чтобы не терять направление.

Исторические sections оставлены там, где они объясняют почему код устроен
именно так. Если нужно общее правило дизайна, сначала смотреть
[`DESIGN.md`](DESIGN.md). Если нужно понять текущую реализацию конкретного
feature, смотреть локальные README и код presenter/ViewModel слоя.

## Главная цель рефакторинга

Первый этап рефакторинга сфокусирован на двух вещах:

1. В первую очередь унифицировать визуальные компоненты и UX.
2. Во вторую очередь разделить backend/presentation/templates через ViewModel
   слой.

Код frontend/SSR слоя должен стать понятным, логичным и компактным. В шаблонах
не должно быть лишнего шума, длинных простыней и повторяющейся разметки для
одинаковых пользовательских паттернов.

Подготовка к будущему переходу на другой frontend stack важна как дальний
ориентир, но не является целью первого этапа. На первом этапе не нужно строить
полноценный API-first или SPA-ready слой, если это усложняет текущий SSR.

## Продуктовый фокус

Booker Tee остается надежным финансовым инструментом для импорта, проверки и
подтверждения финансовых данных. Рефакторинг интерфейса должен усиливать:

- повторяемость пользовательских паттернов;
- финансовую ясность;
- review-first flow;
- аккуратное разделение backend, presentation и templates;
- возможность будущей миграции на другой frontend stack без переписывания
  доменной логики.

## Предварительные архитектурные ориентиры

- Не начинать с абстрактной дизайн-системы.
- Сначала описать ключевые пользовательские сценарии.
- Из сценариев вывести view models и reusable components.
- Jinja-шаблоны должны рендерить готовые presentation/view-model данные, а не
  вычислять бизнес-смысл сущностей.
- HTMX endpoints должны переиспользовать те же partial templates, что и полные
  страницы.
- Существующие URL и финансовое поведение не менять без отдельного решения.

## Решения

- Первый этап: унификация визуальных компонентов и UX.
- Второй приоритет внутри того же направления: ViewModel/presentation слой,
  который упрощает шаблоны и убирает из них вычисления.
- Future frontend stack migration не должна диктовать архитектуру первого этапа.
- Приоритетные экраны для рефакторинга идут от главного financial/review flow к
  вспомогательным и техническим экранам. Текущий статус:
  1. Import review — стабилизирован как эталонный review flow.
  2. Imports flow вокруг review — document detail, mapping, upload/list pages
     приведены к общей геометрии и presenter/ViewModel contracts.
  3. Account detail — переведен на `financial-row`, row actions and row drawer
     pattern; осталась точечная полировка, не новый архитектурный slice.
  4. Manual operations — переведен на `financial-row`, `operation-form`,
     `filter-form` и row drawer pattern; осталась точечная полировка.
  5. Transaction rules — следующий reference CRUD slice. Это самый тяжелый
     экран из rules/categories/properties, потому что он ближе всего к import
     review: правила подсказывают категорию, объект и тип операции, но не должны
     обходить пользовательскую проверку.
  6. Categories / Properties / Users / Workspace operations — следующие
     кандидаты на аккуратную унификацию CRUD/workspace screens после rules.
  7. Reports — отдельный будущий slice для финансовых итогов и таблиц.
- Первый эталонный vertical slice: Import review.
  - Причина: это самый сложный и нагруженный экран; если новый подход выдержит
    его состояния, действия и HTMX-обновления, остальные экраны будет проще
    привести к тому же шаблону.
  - Риск: не превращать первый slice в полный перепил всего review flow. Нужно
    выделить минимальный, но реальный повторяемый компонент и провести его через
    ViewModel + reusable template + HTMX partial.
- Первая единица унификации внутри Import review: Review item + action system.
  - Объем: одна строка импорта, ее финансовое содержание, статус, предложения,
    связь с операцией и доступные действия.
  - Вне первого slice: полная перестройка шапки review page, validation summary,
    workflow steps, mapping и reports.
  - Ожидаемый результат: появится reusable паттерн для будущих financial rows и
    action sets на Account detail и Manual operations.
- Порядок визуального внимания для Review item:
  1. Сумма + направление.
  2. Статус review item.
  3. Описание из выписки.
  4. Дата и счет.
  5. Предложение системы / результат разбора.
  6. Основное действие.
  7. Связь с созданной операцией.
  8. Вторичные действия.
  9. Технические детали.

  Принцип: пользователь сначала понимает деньги и состояние решения, затем
  видит исходное описание и контекст, затем принимает действие. Связь с уже
  созданной операцией важна, но не должна визуально перебивать главное действие,
  кроме состояний, где строка уже проведена и основным фактом является результат
  проведения.
- Review item должен иметь отдельные UX-сценарии для следующих состояний:
  1. `normalized` / `needs_review` — обычная непроверенная строка.
  2. `ready_to_confirm` — категория/объект/тип уже выбраны, строка готова к
     подтверждению.
  3. `suggested` — есть предложение правила или системы.
  4. `possible_duplicate` — похоже на дубль, нужно решение пользователя.
  5. `duplicate` — уже признано дублем.
  6. `confirmed` — строка уже создала операцию.
  7. `matched` — строка связана с существующей операцией.
  8. `ignored` — строка не учитывается.
  9. `failed` / `parse_error` — строка не разобралась или содержит ошибку
     нормализации.

## Review Item Actions

Единая система действий для review item:

| Состояние | Primary | Secondary | Danger |
| --- | --- | --- | --- |
| `normalized` / `needs_review` | Разобрать или Выбрать категорию | Сделать перевод, На проверку, Открыть детали | Игнорировать |
| `ready_to_confirm` | Подтвердить | Изменить категорию/объект, Сделать перевод, Создать правило, На проверку | Игнорировать |
| `suggested` | Подтвердить предложение | Изменить, Посмотреть правило, Сделать перевод, На проверку | Игнорировать |
| `possible_duplicate` | Сравнить | Это новая операция, Связать с существующей, На проверку | Игнорировать |
| `duplicate` | Открыть связанную операцию | Это новая операция, Сравнить, На проверку | Игнорировать / Отвязать |
| `confirmed` | Открыть операцию | Исправить, Открыть источник, Посмотреть проводки | Отменить проведение |
| `matched` | Открыть связанную операцию | Отвязать и разобрать заново, Открыть источник, На проверку | Игнорировать связь / Отменить сопоставление |
| `ignored` | Восстановить | Открыть детали | — |
| `failed` / `parse_error` | Исправить вручную | На проверку, Открыть технические детали | Игнорировать |

Принципы для action system:

- В строке должен быть один визуально главный primary action.
- Secondary actions не должны конкурировать с primary.
- Danger actions отделяются визуально и не смешиваются с обычными действиями.
- Если действие требует выбора или формы, оно может открывать компактный
  details/action panel внутри строки.
- Если строка уже `confirmed` или `matched`, основной акцент смещается с
  подтверждения на результат: открыть связанную операцию и безопасно исправить
  связь.

## Domain Status vs Visual State

`ready_to_confirm` на первом этапе не является доменным backend status и не
должен храниться в базе данных.

Решение:

```text
RawTransaction.status = needs_review / suggested / confirmed / ignored / duplicate / failed / ...
ImportReviewPresenter.visual_state = ready_to_confirm
```

`ready_to_confirm` — presentation-only / computed state. Оно означает:

```text
строка еще не подтверждена,
но данных уже достаточно,
чтобы интерфейс показал primary action "Подтвердить"
```

Правила:

- Не добавлять `ready_to_confirm` в DB enum без отдельного доменного решения.
- Не размазывать вычисление `ready_to_confirm` по Jinja templates.
- Вычислять visual state централизованно в presenter/view-model слое.
- Шаблон получает готовое `visual_state` и только выбирает нужный UI-паттерн.
- В будущем `ready_to_confirm` можно превратить в доменный status, если окажется,
  что его нужно хранить, фильтровать или использовать вне UI.

### Visual State And Confirmability

Важно разделить два понятия:

1. `visual_state` — как строку показываем в UI.
2. `is_confirmable` — можно ли безопасно создать операцию из строки.

`visual_state` вычисляется в presenter и не хранится как отдельный backend
status.

Порядок определения `visual_state`:

1. Финальные состояния:
   - `confirmed`;
   - `matched`;
   - `ignored`;
   - `duplicate`.
2. Ошибки:
   - `failed`;
   - `normalization_error`.
3. Подозрение на дубль:
   - `possible_duplicate`.
4. Активное системное предложение:
   - `suggested`.
5. Если строку уже можно подтвердить:
   - `ready_to_confirm`.
6. Иначе:
   - `needs_review`.

Псевдокод:

```python
def resolve_visual_state(row):
    if row.status == "confirmed":
        return "confirmed"

    if row.status == "matched":
        return "matched"

    if row.status == "ignored":
        return "ignored"

    if row.status == "duplicate":
        return "duplicate"

    if row.status == "failed" or row.normalization_error:
        return "failed"

    if row.status == "possible_duplicate":
        return "possible_duplicate"

    if has_active_suggestion(row):
        return "suggested"

    if can_confirm(row):
        return "ready_to_confirm"

    return "needs_review"
```

`suggested` должен означать именно активное предложение системы, которое
пользователь еще не изменил и не отклонил. Если система предложила категорию по
правилу, но пользователь уже руками изменил категорию/объект, строка становится
`ready_to_confirm`, а не `suggested`.

`is_confirmable = true`, если:

- строка не в финальном состоянии;
- нет blocking `normalization_error`;
- есть `operation_date`;
- есть `amount`;
- есть `currency`;
- есть source account / `account_id` или документ дает достаточный account
  context;
- есть `operation_type`;
- для income/expense есть `category_id`;
- для transfer есть `source_account_id` и `counterparty_account_id`;
- для transfer `source_account_id != counterparty_account_id`.

Псевдокод:

```python
def can_confirm(row):
    if row.status in {
        "confirmed",
        "matched",
        "ignored",
        "duplicate",
        "failed",
    }:
        return False

    if row.normalization_error:
        return False

    if not row.operation_date:
        return False

    if row.amount is None:
        return False

    if not row.currency:
        return False

    if not has_source_account(row):
        return False

    if not row.operation_type:
        return False

    if row.operation_type in {"income", "expense"}:
        return bool(row.category_id)

    if row.operation_type == "transfer":
        return bool(
            row.source_account_id
            and row.counterparty_account_id
            and row.source_account_id != row.counterparty_account_id
        )

    return False
```

Category decision:

- Для первого нормального UX категория обязательна для подтверждения
  income/expense.
- Не подтверждать income/expense в `Uncategorized` fallback по умолчанию.
- Иначе можно легализовать грязные данные:
  - отчеты по категориям станут неточными;
  - `confirmed` начнет означать "проведено, но не разобрано";
  - `needs_review` потеряет смысл.
- Если позже понадобится `Uncategorized` fallback, добавить это отдельно:
  - secondary action "Подтвердить без категории";
  - или workspace setting `allow_uncategorized_confirm`.
- В первом slice:
  - income/expense без `category_id` не confirmable;
  - `visual_state` остается `needs_review`;
  - primary action — "Разобрать" / "Выбрать категорию".

### Operation Type Resolution

Для `operation_type` выбран смешанный подход.

Логика:

1. Если есть явно выбранный/saved `operation_type` — использовать его как
   `explicit`.
2. Если есть `suggested_operation_type` от parser/rule — использовать его как
   `suggested`.
3. Если `operation_type` нет, вывести тип по знаку `amount`:
   - `amount > 0` -> `income`;
   - `amount < 0` -> `expense`;
   - `amount == 0` или `None` -> `unknown`.
4. Такой тип помечать как `inferred`, чтобы UI не притворялся, что это точное
   правило.

В `ReviewItemVM` / `ClassificationVM` нужны поля:

```text
operation_type
operation_type_label
operation_type_source
operation_type_source_label
```

Значения `operation_type_source`:

```text
explicit  — тип выбран/сохранен явно
suggested — тип предложен parser/rule
inferred  — тип выведен по знаку суммы
unknown   — тип определить нельзя
```

`operation_type_source = inferred` можно использовать для UI и для
`ready_to_confirm`, если остальные обязательные поля заполнены.

Пример:

```text
amount < 0 -> inferred expense.
Если есть date, currency, account, category_id и нет blocking errors,
строка может быть ready_to_confirm.
```

В UI нужно показывать источник:

```text
Расход · определено по сумме
```

или мягче:

```text
Скорее всего расход
```

Presenter собирает `operation_type` и source, Jinja только отображает готовые
поля.

### Classification Source

Чтобы отличать активное системное предложение от пользовательской правки,
используем архитектурное поле:

```text
classification_source:
- suggested
- user_selected
- inferred
- none
```

Практический механизм для текущего SSR/HTMX UI:

```text
selected_category_id_by_row
selected_property_id_by_row
selected_operation_type_by_row
```

То есть:

- `classification_source` — архитектурная модель.
- temporary HTMX/request context — механизм определения на первом этапе.

Финальное правило:

```text
visual_state = suggested только когда classification_source = suggested.
```

Если пользователь изменил категорию, объект или тип операции, `visual_state`
больше не `suggested`, а `ready_to_confirm` или `needs_review`.

### SuggestionVM

`SuggestionVM` должен быть структурным, а не только текстовым. Он описывает не
просто "что показать в UI", а "что система предлагает".

```text
SuggestionVM:
- source                 # rule / parser / system
- source_label
- rule_id
- rule_label
- application_mode
- application_mode_label
- pattern
- suggested_category_id
- suggested_category_label
- suggested_property_id
- suggested_property_label
- suggested_operation_type
- suggested_operation_type_label
- confidence_label
- summary
- badge
```

Пример `summary`:

```text
Правило KRASNOE&BELOE предлагает: Расход · Продукты
```

`summary` — готовый текст для UI, но он не заменяет структурные поля.

Почему ids нужны внутри `SuggestionVM`:

1. Presenter должен понимать, что именно предложила система.
2. Можно сравнивать suggestion с пользовательским выбором.
3. Можно корректно определить `classification_source`.

Пример:

```text
если selected_category_id != suggestion.suggested_category_id,
значит classification_source = user_selected,
а visual_state уже не suggested, а ready_to_confirm / needs_review.
```

Разделение ответственности:

- `SuggestionVM` хранит структурное предложение системы:
  `category_id`, `property_id`, `operation_type`, `rule_id`, `pattern`, labels,
  `summary`.
- `CategoryPanelPayload` хранит текущее состояние формы:
  `selected_category_id`, `selected_property_id`, options.
- `ActionVM.hidden_fields` хранит данные, которые нужно отправить при
  конкретном действии: `category_id`, `property_id`, `operation_type`,
  `rule_id`.

`SuggestionVM` не является формой сабмита. Для `confirm_suggestion` presenter
собирает `ActionVM` с нужными `hidden_fields`.

Пример:

```python
ActionVM(
    id="confirm_suggestion",
    label="Подтвердить",
    kind="post",
    tone="primary",
    post_url=confirm_url,
    hidden_fields={
        "category_id": str(suggestion.suggested_category_id),
        "property_id": str(suggestion.suggested_property_id or ""),
        "operation_type": suggestion.suggested_operation_type,
        "rule_id": str(suggestion.rule_id or ""),
    },
)
```

Итог:

- ids нужны;
- labels нужны;
- `summary` нужен;
- отправка данных остается в `ActionVM.hidden_fields` или payload формы панели.

### LinkedOperationVM

В первом slice `LinkedOperationVM` использует summary-based подход.

```text
LinkedOperationVM:
- operation_id
- href
- type
- type_label
- status
- status_label
- date_display
- amount_display
- description
- category_label
- property_label
- route_summary
- entries_summary
- technical_summary
```

`route_summary` — главное человекочитаемое поле для UI.

Примеры:

```text
transfer: "Наличные -> Экспобанк **5017"
income:   "на счет Экспобанк **5017"
expense:  "со счета Экспобанк **5017"
```

На первом этапе не включать money entries как список внутрь
`LinkedOperationVM`. Для review item достаточно готовых summary labels:

- `route_summary`;
- `entries_summary`;
- `technical_summary`.

Причина: review item должен быстро показать, что строка уже проведена/связана и
что именно создано. Детальные money entries лучше открывать через действие
"Открыть операцию" или отдельную future-панель "Посмотреть проводки".

Если позже понадобится показывать проводки прямо в review item, добавить
отдельный `OperationEntriesPanelPayload`, а не раздувать `LinkedOperationVM`.

## Review Item ViewModel

Цель первого implementation slice: привести review item из модуля импорта к
нормальной UI-архитектуре через ViewModel/Presenter.

Нельзя отдавать в Jinja напрямую `RawTransaction` как главный контракт строки и
нельзя размазывать условия по шаблонам. Вместо этого нужен `ReviewItemVM` —
presentation model, которая заранее готовит все, что нужно строке импорта для
отображения.

На первом этапе нужен умеренно плоский вариант, без тяжелой enterprise
иерархии:

```text
ReviewItemVM:
- id
- html_id
- row_index
- visual_state
- domain_status
- is_confirmable
- is_editable
- is_final
- amount_display
- direction
- direction_label
- description
- date_display
- account_label
- result_summary
- category_label
- object_label
- suggestion
- linked_operation
- badges
- problems
- primary_action
- secondary_actions
- danger_actions
- expanded_panel
- css_classes
- technical
```

Допустимые маленькие вложенные структуры:

```text
ActionVM
BadgeVM
ProblemVM
SuggestionVM
LinkedOperationVM
TechnicalDetailsVM
ExpandedPanelVM
```

Для `expanded_panel` выбран смешанный подход.

Изначально планировался один общий `ExpandedPanelVM` как shell:

```text
ExpandedPanelVM:
- type
- title
- subtitle
- payload
- actions
- hints
- css_classes
```

Но `payload` должен быть typed под конкретный сценарий:

```text
CategoryPanelPayload
TransferPanelPayload
DuplicatePanelPayload
TechnicalPanelPayload
ManualFixPanelPayload
```

Не делаем универсальный form-builder с абстрактными `fields`/`sections` на
первом этапе. Это может превратиться в слишком общий и сложный слой.

Реализация первого slice приняла более легкий компромисс: общий shell
существует как `ReviewPanelVM` плюс два partial-уровня `tab + drawer`.
Это дает единое поведение раскрытия, но не заставляет category/transfer формы
подчиняться преждевременному generic `panel.actions`.

Логика:

- `ReviewItemVM` знает, какая панель раскрыта.
- `ReviewPanelVM` описывает общий контейнер панели.
- `panel.type` выбирает partial-шаблон.
- `payload` содержит только данные, нужные конкретной панели.
- panel actions не вводятся, пока реальные формы category/transfer не требуют
  общей footer/action abstraction.

Цель: сохранить простой общий механизм раскрытия панели, но не смешивать разные
UX-сценарии в один generic fields-объект.

Для первого implementation slice входят только:

- `CategoryPanelPayload`;
- `TransferPanelPayload`.

Причина: это две главные пользовательские развилки в review item:

1. Строка является доходом/расходом -> выбрать категорию/объект.
2. Строка является переводом -> выбрать счет-источник и счет-получатель.

Не делаем сразу `DuplicatePanelPayload`, `TechnicalPanelPayload` и
`ManualFixPanelPayload`, чтобы не раздуть первый refactor.

Первый slice должен включать:

- `ReviewItemVM`;
- `ActionVM`;
- `BadgeVM`;
- `ProblemVM`;
- `ReviewPanelVM` как общий shell для tab/drawer;
- `CategoryPanelPayload`;
- `TransferPanelPayload`;
- partial для review item;
- `_panel_tab.html`;
- `_panel_drawer.html`;
- `category_panel.html`;
- `transfer_panel.html`.

Technical details можно пока оставить старым/generic partial или не трогать.
Duplicate и ManualFix вынести во второй этап.

Цель первого slice: сделать стандартный review item и два основных раскрываемых
сценария — "классифицировать" и "сделать перевод".

### CategoryPanelPayload

Для `CategoryPanelPayload` не передавать доменные `Category` / `Property`
напрямую. Presenter должен подготовить option VM.

```text
CategoryPanelPayload:
- document_id
- row_id
- submit_url
- submit_method
- context_summary
- operation_type
- operation_type_label
- selected_category_id
- selected_property_id
- category_options
- property_options
- can_create_category
- create_category_url
- create_category_initial_name
- create_category_error
- category_kind_options
- can_create_rule
- remember_rule_enabled
- rule_pattern_value
- rule_preview
- rule_hint
- submit_label
- cancel_label
```

```text
SelectOptionVM:
- value
- label
- selected
- disabled
- hint
```

Naming decision:

- Старое имя `category_dialog_name` заменено на
  `create_category_initial_name`.
- Старое имя `category_dialog_error` заменено на `create_category_error`.
- Не добавлять `category_dialog_open` на первом шаге.
- Если понадобится открывать форму после ошибки, позже добавить
  `should_open_create_category_dialog`.

### TransferPanelPayload

```text
TransferPanelPayload:
- document_id
- row_id
- submit_url
- submit_method
- context_summary
- amount_display
- direction
- source_account_label
- account_options
- selected_counterparty_account_id
- selected_counterparty_account_label
- transfer_preview
- match_options
- default_match_value
- help_text
- submit_label
- cancel_label
```

```text
TransferMatchOptionVM:
- value
- kind  # new / raw_transaction / existing_operation
- label
- hint
- account_id
- account_label
- candidate_date_display
- candidate_amount_display
- candidate_description
- day_distance_label
- disabled
- selected
```

Field meanings:

- `context_summary`: короткий контекст текущей строки, например
  "Разбираем: -10 000 RUB · 30.06 · Экспобанк".
- `amount_display`: сумма текущей raw transaction, например "-10 000 RUB".
- `direction`: направление текущей raw transaction: income / expense / unknown.
- `source_account_label`: счет из текущей raw transaction.
- `account_options`: список счетов для выбора встречного счета.
- `selected_counterparty_account_id`: выбранный встречный счет.
- `selected_counterparty_account_label`: человекочитаемое название выбранного
  встречного счета.
- `transfer_preview`: готовая строка направления перевода, которую собирает
  presenter, а не Jinja.

Примеры `transfer_preview`:

```text
raw transaction расходная:
source_account_label = "Экспобанк **5017"
selected_counterparty_account_label = "Наличные"
transfer_preview = "Экспобанк **5017 -> Наличные"

raw transaction доходная:
source_account_label = "Экспобанк **5017"
selected_counterparty_account_label = "Наличные"
transfer_preview = "Наличные -> Экспобанк **5017"
```

Важно: в UI перевода пользователь обязательно должен видеть итоговое
направление перевода: откуда -> куда. Это критично для финансового интерфейса.

Шаблон должен только показывать:

```jinja
Будет создан перевод: {{ payload.transfer_preview }}
```

Не собирать направление перевода внутри Jinja. Вся логика направления живет в
presenter.

Принцип: Jinja-шаблон должен быть максимально тупым. Он рисует
`item.amount_display`, `item.badges`, `item.primary_action`,
`item.result_summary`, `item.technical` и другие готовые поля. Логика статусов,
действий, подсказок, ошибок и готовности к подтверждению живет в
presenter/resolver слое.

## Placement

Import review presentation слой живет внутри feature-owned package:

```text
src/app/features/imports/presentation/review/
src/app/features/imports/presentation/document_page/
src/app/features/imports/presentation/mapping/
```

`presentation/review/` является владельцем page context, `ReviewItemVM`,
action policy, labels, panels, reference lookup and state/confirmability
presentation rules.

`presentation/document_page/` и `presentation/mapping/` являются владельцами
page-level VM contracts для document detail и unknown-statement mapping. Старые
одиночные файлы `document_detail.py` / `mapping.py` больше не являются целевым
местом роста для этих экранов.

Текущее размещение:

```text
src/app/features/imports/presentation/review/page.py
src/app/features/imports/presentation/review/item.py
src/app/features/imports/presentation/review/models.py
src/app/features/imports/presentation/review/actions.py
src/app/features/imports/presentation/review/panels.py
src/app/features/imports/presentation/review/labels.py
src/app/features/imports/presentation/review/references.py
src/app/features/imports/presentation/review/state.py
src/app/features/imports/presentation/document_page/models.py
src/app/features/imports/presentation/document_page/presenter.py
src/app/features/imports/presentation/mapping/models.py
src/app/features/imports/presentation/mapping/page.py
src/app/features/imports/presentation/mapping/form.py
src/app/features/imports/presentation/mapping/tables.py
src/app/features/imports/presentation/mapping/preview.py
```

Где:

- `review/page.py` содержит review page-level context/builder.
- `review/item.py` содержит `ImportReviewPresenter` and item orchestration.
- `review/models.py` содержит маленькие VM dataclasses.
- `review/actions.py`, `panels.py`, `labels.py`, `references.py`, `state.py`
  держат отдельные presentation reasons to change.
- `document_page/` содержит document detail VM/presenter.
- `mapping/` содержит page/form/table/preview VM builders для unknown mapping.

## Already Available Data

Поля, которые уже можно заполнить из текущих моделей и context:

- `id`: `RawTransaction.id`.
- `html_id`: `raw-{row.id}`.
- `row_index`: `RawTransaction.row_index`.
- `domain_status`: `RawTransaction.status`.
- `amount_display`: `amount/currency` или fallback на `amount_raw/currency_raw`.
- `direction`: по `amount`: income / expense / transfer_or_unknown.
- `direction_label`: доход / расход / перевод / неизвестно.
- `description`: `description_normalized` или `description_raw`.
- `date_display`: `operation_date` или `operation_date_raw`.
- `account_label`: `row.account.name`, `document.account.name` или
  `account_hint_raw`, если доступно.
- `category_label`: выбранная/предложенная категория.
- `object_label`: предложенный объект/property.
- `suggestion`: из `raw_payload["rule_suggestion"]`,
  `suggested_category_id`, `suggested_property_id`, `suggested_operation_type`,
  `suggested_by_rule_id`.
- `linked_operation`: из `linked_operation_id` и `linked_operation`.
- `badges`: status, visual state, direction, source/suggestion when useful.
- `problems`: `normalization_error` + `balance_chain_problems[row_index]`.
- `technical`: row id, operation id, rule id, row index.
- `css_classes`: `review-item`, `review-item--status-*`, `review-item--next`,
  `hx-swap-oob` flag when needed.

Данные, которые уже приходят в `ReviewPageContext` и нужны для item presenter:

- `categories`;
- `properties`;
- `accounts`;
- `transfer_suggestions`;
- `existing_transfer_suggestions`;
- `balance_chain_problems`;
- temporary UI state after HTMX actions:
  - `selected_category_id_by_row`;
  - `open_category_editor_by_row`;
  - `create_category_error_by_row`;
  - `create_category_initial_name_by_row`.

## Logic Moved Out Of Jinja

Следующая логика была вынесена из legacy review item templates в
presenter/ViewModel слой. Новый `imports/review/_item.html` не должен
возвращать эти вычисления обратно:

- поиск `rule_suggestion` в `row.raw_payload`;
- определение `rule_auto_applied`;
- выбор `row_balance_problems`;
- open/error/name state диалога категории;
- выбор `selected_category_id`;
- поиск предложенной категории и объекта через циклы по `categories` и
  `properties`;
- вычисление первой строки очереди / `review-item--next`;
- вычисление route для linked operation: from/to entry;
- построение summary для transfer/non-transfer linked operation;
- определение ветки UI по статусу, `linked_operation_id`,
  `suggested_by_rule_id`;
- решение, какая кнопка primary/secondary/danger;
- сбор technical details.

Page-level логика также была вынесена из `src/app/templates/imports/review.html`
в `ReviewPageVM` / `ReviewPageContext`:

- вычисление `latest_attempt`;
- `validation`;
- `review_queue`;
- workflow step state.

Новые изменения должны продолжать этот контракт: Jinja рендерит готовые
page/item VM, а не собирает состояние страницы самостоятельно.

## Action Policy

Первый вариант action policy должен быть presentation-level mapping:

```text
visual_state -> primary_action / secondary_actions / danger_actions
```

`ActionVM` должен описывать существующие backend actions, не менять их.

Для `ActionVM` выбран один общий универсальный UI-контракт, а не отдельные
классы `LinkActionVM` / `PostActionVM` / `PanelToggleActionVM`.

```text
ActionVM:
- id
- label
- kind
- tone
- icon
- href
- post_url
- method
- hidden_fields
- target_panel_type
- disabled
- disabled_reason
- confirm_message
- css_classes
- htmx
```

```text
HtmxVM:
- target
- swap
- confirm
```

Разрешенные `kind`:

```text
link
post
panel_toggle
submit_panel_form
```

Смысл `kind`:

1. `link`

   Для обычной навигации:

   - открыть операцию;
   - открыть источник;
   - посмотреть правило.

   Использует `href`.

2. `post`

   Для быстрых действий без раскрытой формы:

   - подтвердить предложение;
   - игнорировать;
   - восстановить;
   - отменить проведение;
   - отправить на проверку.

   Использует:

   - `post_url`;
   - `method`;
   - `hidden_fields`;
   - `confirm_message`;
   - `htmx`.

3. `panel_toggle`

   Для открытия раскрытой панели под review item:

   - разобрать;
   - изменить категорию;
   - сделать перевод;
   - сравнить дубль;
   - открыть технические детали.

   Использует `target_panel_type`.

   Примеры:

   ```text
   category
   transfer
   duplicate
   technical
   manual_fix
   ```

4. `submit_panel_form`

   Для кнопок внутри раскрытой панели:

   - сохранить;
   - сохранить и подтвердить;
   - создать перевод;
   - применить.

   Использует:

   - `post_url`;
   - `method`;
   - `hidden_fields`;
   - `htmx`.
```

На первом этапе `ActionVM` может рендериться Jinja-макросом как ссылка, POST form
или summary/details trigger. Важно не менять существующие endpoints:

- `POST /imports/documents/{document_id}/raw-transactions/{row_id}/status`
- `POST /imports/documents/{document_id}/raw-transactions/{row_id}/undo-posting`
- `POST /imports/documents/{document_id}/raw-transactions/{row_id}/categories`

Существующие backend action strings:

- `confirm`;
- `transfer`;
- `ignore`;
- `mark_unique`;
- `needs_review`;
- `duplicate`.

Invariants:

- Если `kind = link`, должен быть `href`.
- Если `kind = post`, должен быть `post_url`.
- Если `kind = panel_toggle`, должен быть `target_panel_type`.
- Если `kind = submit_panel_form`, действие используется внутри формы панели.
- HTMX-метаданные держать внутри `ActionVM` через `HtmxVM`, а не на верхнем
  уровне `ReviewItemVM`.

Примеры:

```python
ActionVM(
    id="confirm_suggestion",
    label="Подтвердить",
    kind="post",
    tone="primary",
    post_url="/imports/rows/123/confirm/",
    htmx=HtmxVM(
        target="#review-row-123",
        swap="outerHTML",
    ),
)

ActionVM(
    id="edit_category",
    label="Изменить",
    kind="panel_toggle",
    tone="secondary",
    target_panel_type="category",
)

ActionVM(
    id="open_operation",
    label="Открыть операцию",
    kind="link",
    tone="secondary",
    href="/operations/456/",
)

ActionVM(
    id="ignore",
    label="Игнорировать",
    kind="post",
    tone="danger",
    post_url="/imports/rows/123/ignore/",
    confirm_message="Игнорировать эту строку выписки?",
    htmx=HtmxVM(
        target="#review-row-123",
        swap="outerHTML",
    ),
)
```

Цель: Jinja-шаблон не должен решать, какую кнопку рисовать по статусу. Он
получает `item.primary_action`, `item.secondary_actions`, `item.danger_actions`
и рендерит их через общий `action_button` / `action_menu` partial.

### Review Item Action Layout

Primary action:

- Всегда максимум одна.
- Всегда видимая.
- Находится в правой action area.
- Самая заметная.
- Отвечает на вопрос: "что пользователь скорее всего должен сделать сейчас?"

Secondary actions:

- Максимум одна видимая рядом с primary.
- Остальные уходят в меню "Еще".
- Не должны спорить с primary.

Danger actions:

- Никогда не ставить рядом с primary.
- Показывать в меню отдельно после divider.
- Для destructive действий использовать `confirm_message`.

Panel toggles:

- Открывают `expanded_panel` под основной строкой.
- Одновременно у одного item открыта только одна `panel.type`.
- `panel_toggle` не должен сразу менять данные, только раскрывать UI.

Action area:

- Compact.
- Не больше 2 кнопок + меню.
- Если действий много, они уходят в menu.

Если UX-таблица содержит действие, которого backend еще не поддерживает
например `compare`, `link existing`, `unlink`, `open operation`, то в первом
slice оно должно быть либо ссылкой/placeholder action, либо неактивным
secondary action с понятной причиной. Не добавлять новые use cases внутри UI
refactor без отдельного решения.

## Historical Import Review Template Refactor Strategy

Этот section описывает уже выполненный rollout первого import review slice. Он
оставлен как historical note, потому что объясняет происхождение текущего
`ReviewItemVM` contract, HTMX response rendering и review partial placement.

Текущий review item partial живет в feature-owned review folder:

```text
src/app/templates/imports/review/_item.html
```

Первый безопасный подход был таким:

1. Добавить `ReviewItemVM` и builder.
2. В `ReviewPageContext.template_values()` продолжать отдавать старые поля, но
   дополнительно отдать:

   ```text
   review_items
   review_items_by_id
   ```

3. В `imports/review.html` заменить цикл:

   ```jinja
   {% for row in document.raw_transactions %}
   ```

   на:

   ```jinja
   {% for item in review_items %}
   ```

4. В `_review_action_response.html` обновлять `current_item` и sibling items по
   `review_items_by_id`, сохраняя текущую HTMX механику.
5. Переписать `_review_item.html` так, чтобы он читал `item`, а не `row`.
6. Временно оставить сложные вложенные формы, например transfer/category dialog,
   как subcomponents, но передавать им уже подготовленный `item` или
   `item.expanded_panel`.
7. После стабилизации удалить старые template-only вычисления.

Критерий успеха для partial:

```text
_review_item.html не знает, как вычислить visual_state, proposal category,
linked operation route, first queue item, action policy и problem list.
```

### Review Item Layout

Новый review item partial должен использовать такой порядок блоков.

Top line:

- `amount_display`;
- `direction_label`;
- `date_display`;
- status badges;
- action area справа.

Second line:

- `description`.

Meta line:

- `account_label`;
- `row_index`;
- technical/source meta.

Decision line:

- `result_summary`;
- `suggestion.summary`;
- `problems`;
- `linked_operation` summary.

Expanded panel:

- `_panel_tab.html` + `_panel_drawer.html`;
- внутри `category_panel.html` или `transfer_panel.html` по `panel.type`.

Важное правило: дата не должна теряться в мелком meta-тексте вместе с row index.
Row index — техническая деталь, а дата — ключевая финансовая информация. Для
финансового интерфейса дата почти такая же важная, как сумма и направление.

### Template Placement

Новые partials размещаем внутри `imports/review/`.

Причина: review item — доменный компонент модуля импорта, а не универсальный
компонент всего приложения. Поэтому пока не выносим его в `components/domain/`.
Но и не оставляем все partials в корне `imports/`, чтобы не превратить папку в
свалку.

Базовая структура:

```text
src/app/templates/imports/review/_item.html
src/app/templates/imports/review/_actions.html
src/app/templates/imports/review/_panel_tab.html
src/app/templates/imports/review/_panel_drawer.html
src/app/templates/imports/review/panels/_category.html
src/app/templates/imports/review/panels/_transfer.html
```

Можно начать проще:

```text
src/app/templates/imports/review/_item.html
src/app/templates/imports/review/_panel_tab.html
src/app/templates/imports/review/_panel_drawer.html
src/app/templates/imports/review/_category_panel.html
src/app/templates/imports/review/_transfer_panel.html
```

Общие UI partials вынести отдельно:

```text
src/app/templates/ui/_badge.html
src/app/templates/ui/_action_button.html
src/app/templates/ui/_actions_menu.html
src/app/templates/ui/_select.html
```

Правила:

- `imports/review/` содержит доменные partials review item.
- `ui/` содержит базовые переиспользуемые UI-elements.
- `components/domain/` пока не использовать, чтобы не переобобщать раньше
  времени.

### CSS Naming

Для нового review item используем BEM-like naming convention постепенно, только
внутри новых/переписанных компонентов. Не переписывать весь старый CSS проекта.

Целевой основной компонент:

```text
review-item
review-item--state-needs-review
review-item--state-ready-to-confirm
review-item--state-suggested
review-item--state-confirmed
review-item--state-matched
review-item--state-ignored
review-item--state-duplicate
review-item--state-failed
```

Внутренние элементы:

```text
review-item__body
review-item__main
review-item__topline
review-item__money
review-item__amount
review-item__direction
review-item__date
review-item__badges
review-item__description
review-item__meta
review-item__decision
review-item__suggestion
review-item__problem
review-item__linked-operation
review-item__actions
review-item__panel
```

Expanded panel:

```text
review-panel
review-panel--type-category
review-panel--type-transfer
review-panel__header
review-panel__title
review-panel__subtitle
review-panel__body
review-panel__actions
review-panel__hint
```

Action area:

```text
review-actions__system
review-actions__primary
review-actions__secondary
review-actions__menu
review-actions__danger
```

Правила:

- Новые review partials используют BEM-like classes.
- Старую верстку не трогать без необходимости.
- Для текущего stabilized slice используются `review-item--vm`,
  `review-item__*`, `review-panel__*` и `review-actions__*`; старые внутренние
  классы остаются как compatibility layer.
- При следующем UI touch point опираться на новые owner-class контракты и не
  добавлять новые правила только к старым review item fallback-селекторам.
- Целевой state modifier строится из `visual_state`:

  ```jinja
  review-item--state-{{ item.visual_state }}
  ```

## Acceptance Criteria For First Slice

Первый implementation slice считается готовым, если:

1. Review item рендерится из `ReviewItemVM`, а не напрямую из
   `RawTransaction`.
2. `_item.html` не вычисляет:
   - `visual_state`;
   - `is_confirmable`;
   - `suggestion`;
   - `classification_source`;
   - `route_summary` / `transfer_preview`;
   - actions;
   - problems;
   - badges.
3. В шаблоне допускается только простое отображение:
   - `item.amount_display`;
   - `item.direction_label`;
   - `item.date_display`;
   - `item.description`;
   - `item.account_label`;
   - `item.badges`;
   - `item.result_summary`;
   - `item.primary_action`;
   - `item.expanded_panel`.
4. `CategoryPanelPayload` и `TransferPanelPayload` работают через typed payload.
5. `ReviewPanelVM` используется как общий shell:
   - `panel.type`;
   - `panel.title`;
   - `panel.payload`;
   Конкретное содержимое рендерится через category/transfer partial.
   В первом slice `panel.actions` не вводится: category и transfer панели
   используют собственные form contracts.
6. Primary/secondary/danger actions приходят из presenter/action policy, а не
   собираются в Jinja.
7. В review item визуально есть максимум:
   - 1 primary action;
   - 0-1 visible secondary action;
   - остальные secondary/danger actions в меню.
8. Danger actions отделены от обычных actions и для destructive действий имеют
   `confirm_message`.
9. HTMX update строки после action работает как раньше:
   - confirm;
   - ignore;
   - restore;
   - open category panel;
   - open transfer panel;
   - submit category panel;
   - submit transfer panel.
10. Одновременно у одного review item открыта только одна expanded panel.
11. Существующие review template tests проходят или осознанно обновлены под новый
    partial.
12. Добавлены unit tests для:
    - visual_state resolver;
    - `is_confirmable`;
    - action policy;
    - `operation_type_source`;
    - `classification_source`;
    - `transfer_preview`.
13. Не меняются:
    - DB enum;
    - финансовая логика posting;
    - URL endpoints;
    - модели БД;
    - бизнес-логика создания операций.
14. `ready_to_confirm` остается presentation-only состоянием, не backend status.
15. Income/expense без категории не confirmable.
16. Transfer confirmable только если:
    - есть source account;
    - есть counterparty account;
    - source account != counterparty account.
17. Transfer preview всегда показывает направление "откуда -> куда".
18. Date отображается в top line review item, не прячется в техническую
    meta-информацию.
19. Row index / raw id / technical details не конкурируют визуально с суммой,
    датой, статусом и описанием.
20. Новый CSS использует BEM-like naming для стабилизированных новых частей:
    - `review-item__*`;
    - `review-panel__*`;
    - `review-actions__*`.
    Root нового item помечен как `review-item--vm`. Старые item-only CSS
    fallback-селекторы удалены после `review_interactions` audit.
21. Новый partial можно включить точечно вместо старого review item без
    переписывания всего модуля импорта.
22. Если что-то ломается, старый partial можно временно вернуть без миграций БД
    и отката бизнес-логики.

### Current Acceptance Audit

Состояние на 2026-07-06 после stabilization cleanup первого import review slice.

| # | Status | Evidence / note |
| --- | --- | --- |
| 1 | Closed | `review.html` рендерит `review_items`; `_item.html` получает `item`; `ReviewItemVM` больше не хранит raw `row`; есть guard test на отсутствие `item.row` / `document` / `use_review_item_vm` в `_item.html`. |
| 2 | Closed | `visual_state`, confirmability, proposal summary, action policy, problems и badges собираются в `presentation/review/*`; `_item.html` только отображает подготовленные поля и коллекции. |
| 3 | Closed | Template отображает текущие VM-поля (`amount_label`, `date_label`, `account_label`, badges, summary, actions, panels). Имена отличаются от раннего sketch, но ответственность соблюдена. |
| 4 | Closed | `CategoryPanelPayload` и `TransferPanelPayload` являются typed payload внутри `ReviewPanelVM`; category/property/account options подготовлены presenter-слоем. |
| 5 | Closed by adjusted design | Общий shell реализован как `ReviewPanelVM + _panel_tab.html + _panel_drawer.html`; `panel.actions` сознательно не введен для первого slice. |
| 6 | Closed | `ReviewActionPolicy` собирает `primary`, `visible_secondary`, `menu`, `danger`; Jinja не принимает action-policy решений. |
| 7 | Closed | `ActionSetVM` структурно ограничивает 0-1 primary и 0-1 visible secondary; template уводит остальные actions в menu/danger. |
| 8 | Closed | Danger actions рендерятся отдельно; destructive actions имеют `confirm_message`; covered by presentation/template tests. |
| 9 | Mostly covered | HTMX response renderer and template tests cover row/OOB refresh and category-create refresh. `scripts/ui_audit.py --scenario review_interactions` covers panel opening/category refresh and one visible drawer. Full browser coverage for every listed action, especially transfer submit, should remain a follow-up. |
| 10 | Closed | Alpine state uses one `activePanel` per item; UI audit checks that opening a panel leaves exactly one visible drawer. |
| 11 | Closed | Existing review template tests were adapted and expanded around VM rendering and action response values. |
| 12 | Closed | Unit/template tests cover visual state, confirmability, action policy, operation type source labels, panel behavior and `transfer_preview` rendering. |
| 13 | Closed | First slice changed presentation/templates/routes composition only; no DB enum/model/posting URL behavior was intentionally changed. |
| 14 | Closed | `ready_to_confirm` is produced by `ReviewStateResolver`; `RawTransaction.status` remains unchanged. Covered by `test_ready_to_confirm_is_presentation_only_state`. |
| 15 | Closed | `ReviewConfirmabilityPolicy` rejects income/expense without a real category, including uncategorized fallback. |
| 16 | Closed | `ReviewConfirmabilityPolicy` requires source account, counterparty account, and different accounts for transfer. |
| 17 | Closed | `TransferPanelPayload.transfer_preview` exposes a server-built route label. Positive raw rows preview as `выбери счет -> счет выписки`; negative rows preview as `счет выписки -> выбери счет`. |
| 18 | Closed | Date is in the top line via `review-item__date`; covered by template assertions around `review-item__topline`. |
| 19 | Closed | Row index is small meta; raw id is not surfaced as primary content; technical details do not compete with money/date/description in the current item layout. |
| 20 | Closed | Stabilized new parts use `review-item__*`, `review-panel__*`, `review-actions__*`, and `review-item--vm`. Older item/dialog fallback selectors were removed from `app.css` after `review_interactions` audit. |
| 21 | Closed | New active rendering path uses `imports/review/_item.html` and `ReviewItemVM`; old raw-transaction review item fallback was removed after stabilization. |
| 22 | Superseded | Initial rollback criterion was useful during the feature-flag phase. After stabilization, the old partial and `use_review_item_vm` were removed by decision; rollback would now be a normal git revert, not a runtime switch. |

## Gradual Migration Plan

Не переписывать весь frontend сразу.

### First Slice Implementation Note

После первого implementation slice import review использует активный
`ReviewItemVM`-рендеринг без legacy RawTransaction partial fallback.

Панели review item стабилизированы как UX-модель `tabs + drawers`, а не как
единый универсальный panel shell:

- `ReviewPanelVM` описывает панель review item;
- `_panel_tab.html` отвечает за кнопку панели;
- `_panel_drawer.html` отвечает за drawer-оболочку и подключение typed partial;
- `_category_panel.html` и `_transfer_panel.html` остаются владельцами
  конкретного содержимого и форм;
- `panel.actions` пока не вводится, потому что category и transfer panels имеют
  разные form contracts и не требуют общей action footer abstraction.

Новый CSS для item/panel/action слоя мигрирует к BEM-like naming постепенно:

- `review-item__*`;
- `review-panel__*`;
- `review-actions__*`.

`imports/review/_item.html` больше не смешивает старые item-only classes с
`review-item__*`. Shared legacy leaks уже разобраны: warning/signal lists в
imports/mapping используют `ui-signal-list`, account detail использует
`account-entry__meta`, а root `review-actions` больше не нужен как CSS
container. Старые item fallback-селекторы (`review-status-*`, `review-main`,
`review-topline`, `review-state-*`, `review-signal-*`, `review-ledger-*`,
`review-panels`, `review-dialog-*`) удалены из `app.css` после
`review_interactions` audit.

Шаги:

1. Добавить VM dataclasses и presenter tests без изменения HTML.
2. Подключить `review_items` параллельно старым `row`.
3. Переписать только `_review_item.html` на `item`.
4. Оставить `review.html`, `_review_next_step.html`, validation summary и workflow
   почти без изменений.
5. Обновить existing template tests под новый contract.
6. Добавить unit tests для visual-state resolver и action policy.
7. После этого перенести тот же паттерн на Account detail и Manual operations.

## Implementation Guardrails

- Не менять DB enum для `ready_to_confirm`.
- Не менять финансовое поведение и posting use cases в рамках UI refactor.
- Не удалять raw source/debug данные.
- HTMX response должен по-прежнему возвращать обновленную строку и next-step
  partial.
- Старые tests вокруг review template являются полезным safety net; их лучше
  адаптировать, а не удалять.
- Presenter может работать с ORM objects на первом этапе, но наружу в template
  должен отдавать только VM.

## Completed Review Item Rollout Note

Первый implementation slice выполнил временный feature-flag rollout:

- `use_review_item_vm` удален;
- legacy `RawTransaction`-based review partial fallback удален;
- active review rendering идет через `imports/review/_item.html`;
- `_item.html` получает подготовленный `ReviewItemVM`;
- rollback теперь является обычным git revert, а не runtime switch.

Новые изменения не должны возвращать параллельную ветку `row`/`item` в Jinja.
Если нужен новый безопасный rollout, он должен быть спроектирован отдельно и
иметь явный срок удаления.

## Current Open Plan

Ближайшие направления после закрытия import review, imports flow convergence,
account detail and manual operations slices:

1. Продолжать точечную CSS/BEM миграцию только при реальной работе с экраном:
   не переписывать naming ради naming.
2. Довести вспомогательные CRUD/workspace screens до общего языка. Первый
   следующий slice: transaction rules (`/rules`), затем categories/properties,
   позже users/workspaces. Перед началом каждого slice сверяться с `DESIGN.md` /
   `Working Screen Contract`.
3. Выделить reports как отдельный financial-summary/table slice.
4. Shared action contract уже начат через `app.shared.ui.actions.ActionVM` and
   `ui-action__*` classes. Дальше усиливать только там, где несколько features
   повторяют один и тот же action pattern; не переносить feature-specific
   бизнес-решения в общий UI слой.
5. Не вводить универсальный financial-row partial, пока account/manual/import
   варианты не покажут стабильный повтор без потери смысла.

## Reference CRUD Slice: Transaction Rules First

Следующий frontend/SSR refactor slice начинается с `/rules`, а не с более
простых categories/properties. Причина: transaction rules — самый нагруженный
reference screen и одновременно часть review workflow. Если здесь получится
убрать шум форм, выстроить action hierarchy и вынести presentation state из
Jinja без потери ясности, остальные reference screens можно будет привести к
тому же языку меньшими шагами.

Цель первого rules slice:

- список правил становится главным содержанием экрана;
- создание правила становится page action / compact accordion, а не большой
  формой, которая доминирует над списком;
- редактирование правила открывается как действие на строке/card, а не
  постоянно занимает место внутри каждого item;
- в строке есть один primary action, спокойные secondary actions и отдельно
  danger action;
- шаблон получает подготовленные labels, title, meta chips, action state and
  form ids, а не вычисляет category-vs-operation-type fallback сам;
- правила остаются suggestion/autofill механизмом и не обходят import review или
  ledger invariants.

Первый implementation slice для `/rules` не должен:

- менять DB schema, rule matching, fixture seeding или import review behavior;
- вводить универсальный CRUD component для categories/properties/users;
- удалять старые `entity-card` / `form-panel-embedded` classes глобально;
- переписывать categories/properties в том же PR/turn;
- превращать transaction rules в отдельный AI/automation flow.

Ожидаемая архитектурная форма:

```text
router.py
  -> application use cases / query use case
  -> presentation RuleRowVM / RulesPageVM
  -> feature-owned Jinja partials
```

`transaction_rules` уже имеет `application/` and `domain/`, поэтому новый слой
должен быть маленьким `presentation/`, только для UI state. Если в процессе
окажется, что достаточно локального presenter-free cleanup, это решение нужно
зафиксировать перед кодом, а не создавать ViewModel ради симметрии.

## Known Scale UX Risks Before Release

Этот раздел фиксирует риски, которые могут быть почти незаметны на небольших
данных, но неожиданно ударить при реальном использовании. Это не список “сделать
сразу”, а карта наблюдения и будущих optimization/refactor slices.

### P1: Check Before Release

#### Category Detail Can Become Heavy

Current state:

- `categories/detail.html` renders all confirmed operations for a category in a
  single table.
- There is no pagination or compact financial-row listing on the category detail
  operation table.

Why it matters:

- Categories such as groceries, cafes, marketplace, transport or subscriptions
  can collect hundreds or thousands of operations faster than rules/properties.
- This page can become the first reference screen where SSR HTML size, table
  rendering and browser scrolling feel slow.

Before release:

- test category detail with a large realistic category;
- check desktop and mobile scroll/readability;
- check whether the table still helps scanning or becomes noise.

Preferred future direction:

- add pagination/filtering or reuse a compact financial-row list;
- keep technical details secondary;
- avoid building a separate report-like mega table inside category detail.

#### Form Error UX Outside Import Review

Current state:

- Import review has the strongest HTMX/partial feedback story.
- Many CRUD/reference forms still raise plain `400` errors for validation or
  duplicate-name cases.

Why it matters:

- Release users will make ordinary mistakes: duplicate category, empty name,
  invalid date, invalid category/property id, archived entity action.
- A raw error page feels like data loss or system failure even when the backend
  correctly rejected the action.

Before release:

- manually test common bad inputs on `/rules`, `/categories`, `/properties`,
  `/ledger/manual`, account detail correction, import review category creation;
- decide which raw errors are acceptable for private MVP and which need inline
  handling before release.

Preferred future direction:

- use feature-owned partial/form response for expected validation errors;
- preserve non-HTMX redirect/error fallback;
- keep domain/data safety errors explicit and boring.

#### Redirect-Driven Row Actions Still Exist

Current state:

- Import review and transaction rules now have local HTMX updates for important
  row/list actions.
- Manual operations now replace the affected row locally after save, cancel, or
  restore, and remove the row locally after delete.
- Account detail imported-operation corrections now replace the affected
  movement row locally after save.
- Categories and properties still mostly use full-page redirects after
  row-level changes.

Why it matters:

- The data remains correct, but the user can lose local context: drawer closes,
  scroll jumps, filters reset or the row focus changes.
- This is more noticeable during repeated cleanup work.

Before release:

- verify the main correction workflows are still understandable despite reloads;
- do not start a broad rewrite unless a workflow is clearly painful.

Preferred future direction:

- apply the `Entity Feedback And Local Update Contract` from `DESIGN.md`;
- convert one workflow at a time to row/list partial updates;
- keep redirect fallback.

#### Highlight Semantics Rollout

Current state:

- Transaction rules, account detail, manual operations and import review have
  started following the highlight contract from `DESIGN.md`.
- Calm statuses such as confirmed, imported, parsed, matched, normalized and
  ready-to-confirm use muted badges/tokens instead of success colors.
- Transaction rule `active` is a calm live-status badge: visible enough to show
  that the rule is enabled, but quieter than money, problems and primary
  actions.
- Account/manual row categories use a dedicated `classification` chip instead
  of income/expense colors; warning/problem states still stay visible.
- Transfer amounts use transfer color by operation type, not by the sign of the
  account leg; transfer routes use the same `classification` chip family as
  categories.
- Import review still keeps financial tones for money and operation type, and
  keeps problem states noticeable.

Remaining watch points:

- Categories/properties/reference screens still need the same review when they
  get their card/form refactor.
- Avoid reintroducing green `confirmed` badges in templates; normal states
  should be readable, not celebratory.

### P2: Near-Term UX/Scale Debt

#### Hidden Row Forms In Long Lists

Current state:

- Some list rows include edit forms and repeated select options even when the
  drawer/panel is closed.
- Examples:
  - transaction rules now lazy-load edit drawer content via HTMX;
  - manual operation rows now lazy-load edit drawer content via HTMX;
  - account movement rows now lazy-load imported correction drawers via HTMX;
  - import review still pre-renders review panels; treat lazy review panels as a
    separate optimization slice because they are coupled to review actions and
    panel state;
  - properties currently render edit fields directly inside each card.

Why it matters:

- At 50-200 rows, repeated categories/properties/account selects can produce a
  much larger DOM than the visible content suggests.
- The page may feel slow even if the database query is fine.

Preferred future optimization:

- repeat the transaction rules lazy drawer pattern when a row carries heavy
  closed form markup;
- render only the information/action shell initially;
- cache/reuse reference options where appropriate.

Avoid as first response:

- pagination only to hide repeated form weight. Pagination can hurt reference
  workflows and does not fix heavy per-row markup.

#### Properties Screen Is Still Admin-Heavy

Current state:

- `properties/index.html` renders edit fields directly in every property card.
- Actions are not yet aligned with the Entity Work Row language.

Why it matters:

- Objects/properties may start small, but the screen will feel noisy as soon as
  there are multiple properties/projects.
- It is likely to inherit the same created-entity and local-update needs as
  transaction rules.

Preferred future direction:

- convert to Entity Work Row geometry;
- create form as a page action/compact accordion;
- edit as row drawer;
- use Created Entity Feedback Pattern;
- keep archive/restore secondary and danger actions separated.

#### Created Entity Feedback Should Spread To Reference Screens

Current state:

- Transaction rules now use a recent-created feedback pattern.
- Categories/properties do not yet use it.

Why it matters:

- In a long reference list, “created successfully” is not enough; the user needs
  to know what was created and how to find it.

Preferred future direction:

- for categories/properties/users/workspaces, pass `recent_entity_id` into the
  list partial after create;
- show compact feedback above the list;
- highlight the created row calmly;
- provide a stable anchor link.

#### Filters After Mutating Actions

Current state:

- Transaction rules have list filters and local list replacement.
- Transaction rule delete/load-more actions preserve the active query state
  through the list partial URL.
- Other screens may still return the default list if the active filter state is
  not carried through hidden fields/query parameters.

Why it matters:

- A user can filter a list, then create/delete/toggle and suddenly see a
  different list context.

Preferred future direction:

- preserve active filter query state in list-level mutating actions;
- for row-level updates, prefer replacing only the affected row when possible;
- when an action removes a row from the current filter result, show a calm list
  update rather than a surprising jump.

### P3: Observe, Do Not Prematurely Build

#### Transaction Rules Pagination

Current stance:

- Do not use numbered pagination for ~69 rules.
- Transaction rules use search/filter, created feedback, lazy edit drawers and a
  bounded `Show more` list to avoid rendering an unbounded SSR list.

Watch for:

- 300-500+ rules;
- large category/property option sets;
- browser audit showing slow initial render or sluggish interaction;
- HTML response size becoming noticeably large.

Preferred order if it becomes a problem:

1. keep lazy edit drawers;
2. keep server-side filtering and bounded `Show more`;
3. consider numbered pagination only if the visible row count itself becomes the
   problem.

#### Manual/Account Per-Page Upper Bound

Current state:

- Manual operations and account detail support pagination up to 200 rows.
- Rows can include drawer/correction form controls and repeated select options.

Watch for:

- slow rendering at `per_page=200`;
- mobile scroll fatigue;
- correction drawer sluggishness.

Preferred future direction:

- keep default page size moderate;
- lazy-load heavy drawers if needed;
- keep filters compact and secondary.

#### Template Presentation Logic In Legacy Reference Screens

Current state:

- Categories still group rows in Jinja with `selectattr` and local macro logic.
- Category detail still computes some display choices in templates.

Why it matters:

- This is acceptable for a simple MVP screen, but it resists consistent action
  hierarchy, created feedback and local updates.

Preferred future direction:

- when touching categories, introduce a small presenter/page VM;
- do not create a universal CRUD component;
- preserve existing backend/service behavior.

---------------

## Imports Flow UI/UX Convergence Note

The imports flow now uses the import review screen as the visual and
architectural reference:

```text
upload -> document detail -> mapping, if needed -> review -> ledger/report context
```

Current stabilized contracts:

- import review renders through `ReviewItemVM`, `ReviewPanelVM`, typed category
  and transfer payloads, and the action system;
- document detail renders through `presentation/document_page/` page-level VMs;
- unknown-statement mapping renders through `presentation/mapping/` page, form,
  table and preview VMs;
- upload, document detail, mapping, index and review share the same broad
  geometry: context/status/facts first, next-step/actions in a predictable
  action area, technical/debug details collapsed and visually secondary;
- touched controls migrate to BEM-like owner naming such as `review-item__*`,
  `review-actions__*`, `review-panel__*`, `import-action-details__*`,
  `import-document-card__*`, `mapping-table-picker__*`,
  `mapping-action-row__*` and `import-upload-form__*`;
- raw source/debug data remains available, but it should not dominate the first
  screen.

Guardrails that remain in force:

- do not change URL endpoints, parser behavior, DB models/enums, or ledger
  posting rules as part of UI/SSR convergence;
- do not delete raw source/debug data;
- do not rewrite all CSS for naming alone;
- keep presenter/ViewModel ownership over status/action policy and page copy;
- migrate old generic classes only when touching the related UI for product or
  maintainability reasons.

Validation note:

`validation_report_json` is refreshed through the review/status update flow. If
old documents appear with stale validation reports, handle that as a separate
repair/migration task rather than mixing it into UI/SSR refactor work.

Completion gate for imports-flow UI work:

- focused presenter/template tests pass for touched flows;
- `ruff`, `ty` and `git diff --check` pass for touched code;
- `scripts/ui_audit.py --scenario realistic` passes for everyday smoke checks;
- reserve `button_audit` for deliberate action-system changes or a final broad
  pass;
- desktop/mobile screenshots show no accidental horizontal overflow, no
  prominent technical/debug blocks on first screen, and consistent primary /
  secondary action hierarchy.

## Account Detail Refactor Note

Implemented UI/SSR slice after imports flow convergence: account detail.

Decision:

- account detail should not invent a separate transaction/timeline geometry;
- it should reuse the shared financial row rhythm proven by import review;
- the screen is a ledger movement list, not a review queue, so row actions have
  a different meaning while keeping the same placement and hierarchy.

Target row shape:

```text
amount + date + operation type + status       result/action zone
description
category/property or transfer route/source
technical details collapsed
```

Right-side row zone:

- always reserved for result summary and actions;
- shows the operation result compactly, for example `расход · Продукты` or
  `ВТБ вклад -> Экспобанк карта`;
- should not duplicate the whole operation as a heavy nested card;
- should keep primary action, secondary action and more/technical action in a
  predictable order.

Editing:

- edit actions should open a row-level drawer/panel under the movement;
- the drawer spans the row width instead of squeezing forms into the right
  action column;
- imported operations and manual operations may have different forms, but the
  drawer shell should feel like the same interaction pattern.

Architecture direction:

- move account detail presentation decisions out of Jinja into a
  presenter/ViewModel slice;
- keep URL endpoints, ledger posting rules, DB models and operation lifecycle
  unchanged;
- migrate CSS toward owner BEM names when touching this screen, without a broad
  naming-only rewrite.

### Account Detail Implementation Status

Первый безопасный vertical slice уже реализован:

1. Account detail presentation package exists:

   ```text
   src/app/features/accounts/presentation/detail/
     models.py
     presenter.py
   ```

   Current VMs:

   - `AccountDetailPageVM`;
   - `AccountDetailAccountVM`;
   - `AccountDetailMetricVM`;
   - `AccountMovementVM`;
   - `AccountMovementBadgeVM`;
   - `AccountMovementMetaVM`;
   - `OperationResultVM`;
   - `AccountMovementActionVM`;
   - `AccountMovementDrawerVM`;
   - `AccountDetailPresenterInput`.

2. Presentation decisions moved out of `accounts/detail.html`:

   - active filter state;
   - amount direction and money CSS class;
   - result summary text;
   - transfer route text;
   - source-specific actions;
   - raw import source link;
   - whether a movement has an edit drawer and which drawer type it uses.

3. Dumb account detail partials exist:

   ```text
   src/app/templates/accounts/detail/_movement.html
   src/app/templates/accounts/detail/_movement_actions.html
   src/app/templates/accounts/detail/_movement_drawer.html
   ```

   The partials should render prepared VM fields. They should not inspect
   `entry.operation.source.value`, choose from `raw_transactions[0]`, compute
   amount sign, or search money entries.

4. Heavy nested operation rendering in movement rows was replaced:

   - remove `operation_ref(...)` from the normal movement row path;
   - keep a compact right-side result/action zone;
   - preserve source links and technical operation IDs behind secondary or
     technical details.

5. Row-level edit drawer shell exists:

   - drawer opens from the right action zone;
   - drawer spans the movement width under the row;
   - imported operation drawer can edit description/status/category/property
     and link back to the import row;
   - manual operation may initially link to `/ledger/manual?...` instead of
     duplicating the full manual edit form in this slice.

6. Touched CSS migrated toward account-owned BEM names:

   ```text
   account-movement
   account-movement__main
   account-movement__topline
   account-movement__amount
   account-movement__meta
   account-movement__result
   account-movement__actions
   account-movement__drawer
   ```

   Keep compatibility classes only where another screen still depends on them.
   Do not rewrite unrelated `entity-card`, `manual-operation`, or import review
   CSS just for naming consistency.

7. Focused tests cover the slice:

   - presenter tests for income, expense, transfer, imported/manual/system
     sources;
   - template tests proving movement rows render prepared VM data;
   - regression test that normal movement rows do not use the old heavy
     `operation-ref` block;
   - account detail template keeps technical IDs collapsed.

Recommended checks when touching this slice:

   ```bash
   uv run pytest tests/features/accounts/test_account_detail_template.py
   uv run pytest tests/features/accounts/test_accounts_template.py
   uv run ruff check .
   uv run ty check .
   git diff --check
   uv run python scripts/ui_audit.py --scenario realistic
   ```

Remaining account detail follow-up:

- continue small UI/CSS cleanup only when touching the screen;
- keep filters/settings compact and secondary;
- do not reintroduce the old heavy `operation-ref` row card.

Still out of scope unless explicitly requested:

- changing ledger posting behavior;
- changing URL endpoints;
- changing DB models/enums;
- rebuilding manual operations inline editing completely;
- designing a new timeline-only geometry;
- broad CSS renaming outside the touched account detail surface.

## Manual Operations Refactor Note

Implemented UI/SSR slice after account detail: manual operations.

Decision:

- manual operations should continue the same financial row/action/drawer
  language used by import review and account detail;
- the page is a creation and correction workflow, not a review queue;
- manual operations have stronger edit powers than imported-operation review:
  type, amount, account, date, category, property and description can change;
- lifecycle actions (`cancel`, `restore`, `delete`) must stay explicit and
  visually separated from ordinary edits.

Original problems in the screen:

- `ledger/manual.html` owns too many presentation decisions directly in Jinja;
- the page mixes create form, filters, operation rows, edit forms and lifecycle
  actions in one long template;
- operation rows still use old `entity-card` geometry instead of the shared
  `financial-row` rhythm;
- edit forms are always visible inside each operation card, which makes the
  page feel heavy even before the user chooses to edit anything;
- filter form duplicates account-detail filter concepts but uses older layout
  and action hierarchy;
- the template computes display currency, amount tone, transfer route/source
  labels and action availability inline.

Target page shape:

```text
Page header
Create manual operation form
Filter accordion
Manual operation rows
```

Target manual operation row:

```text
date                                      amount
description
category/property or transfer route · account context · calm status
right side: primary edit action, lifecycle actions, technical details collapsed
drawer: edit form only when opened
```

Architecture direction:

- add a small ledger presentation package for this page instead of growing
  `ledger/router.py` or adding more template logic;
- keep manual operation write use cases, URL endpoints, DB models/enums and
  lifecycle behavior unchanged;
- keep the first slice behavior-preserving and focused on ViewModel/template
  boundaries;
- do not create a generic universal row component before the account detail and
  manual operation variants prove which fields are truly shared.

### Manual Operations Implementation Status

Первый безопасный vertical slice уже реализован:

1. Manual operations presentation files exist:

   ```text
   src/app/features/ledger/presentation/manual_operations/
     models.py
     presenter.py
   ```

   Current VMs:

   - `ManualOperationsPageVM`;
   - `ManualOperationRowVM`;
   - `ManualOperationMetaVM`;
   - `ManualOperationActionVM`;
   - `ManualOperationDrawerVM`.

2. Row presentation decisions moved out of `ledger/manual.html`:

   - display currency;
   - amount direction / money tone;
   - date label;
   - description fallback;
   - transfer route;
   - account context label;
   - category/property/status meta;
   - current/focused row state;
   - inactive/cancelled row state;
   - available primary, lifecycle and danger actions.

3. The create form stayed behavior-preserving:

   - preserve existing POST endpoint and form field names;
   - preserve segmented operation type behavior;
   - do not change transfer validation or posting rules;
   - only add owner classes / small layout improvements if needed for the new
     page structure.

4. Manual operation partials exist:

   ```text
   src/app/templates/ledger/manual/_row.html
   src/app/templates/ledger/manual/_row_actions.html
   src/app/templates/ledger/manual/_row_drawer.html
   src/app/templates/ledger/manual/_filters.html
   ```

   Keep the partial count small. Add a partial only when it removes a real
   repeated or noisy story from `manual.html`.

5. The operation list was converted from old `entity-card` rendering to the
   shared financial-row pattern:

   - date and amount in the top line;
   - description as the main human-readable text;
   - category/account/status metadata below;
   - technical ID collapsed;
   - right-side actions in `row-actions`;
   - edit form moved to a row drawer.

6. Edit behavior was reworked:

   - row shows a calm `редактировать` primary action;
   - edit form appears only in the drawer;
   - lifecycle actions stay visible but secondary;
   - destructive delete remains danger and should keep explicit user intent.

7. Filters were brought closer to account detail:

   - use the same compact accordion rhythm;
   - use `inline_hint` only if the copy carries real guidance;
   - keep primary `применить` and secondary `сбросить` hierarchy;
   - preserve all query parameter names and pagination behavior.

8. Focused tests cover the slice:

   - presenter tests for income, expense and transfer rows;
   - presenter tests for confirmed vs ignored lifecycle actions;
   - template tests proving rows render prepared VM fields;
   - regression tests for create/edit/cancel/restore/delete form actions;
   - URL helper tests for filters and focused operation anchors.

Recommended checks when touching this slice:

   ```bash
   uv run pytest tests/features/ledger/test_manual_operations_template.py
   uv run pytest tests/features/ledger/test_ledger.py
   uv run ruff check .
   uv run ty check .
   git diff --check
   uv run python scripts/ui_audit.py --scenario realistic
   ```

Remaining manual operations follow-up:

- continue small UX/CSS cleanup after real use;
- keep `filter-form` compact and secondary;
- avoid bringing always-visible edit forms back into rows;
- keep lifecycle actions separated from ordinary edit actions.

Still out of scope unless explicitly requested:

- changing ledger posting behavior;
- changing URL endpoints or form field names;
- changing DB models/enums;
- introducing JSON API or SPA behavior;
- replacing the existing segmented operation type behavior;
- broad CSS renaming outside touched manual operation UI;
- making a universal shared financial-row partial for every feature.
