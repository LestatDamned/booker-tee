# REFACTOR_PROJECT_DESIGN.md — Frontend Refactor Anchor

Живой документ для подготовки и проведения рефакторинга frontend/SSR слоя Booker Tee.

```text
Status: active implementation plan
Read when: working on import review, ReviewItemVM, action policy, or SSR frontend refactor
Do not use as: general product roadmap
```

Цель документа: собрать решения до начала больших правок, чтобы рефакторинг был
последовательным, проверяемым и не превращался в серию случайных переделок.

## Рабочий процесс

1. Codex задает один вопрос за раз.
2. Пользователь отвечает в свободной форме.
3. Codex обновляет этот документ: фиксирует решение, уточняет риски и добавляет
   следующие открытые вопросы.
4. Когда решений достаточно, документ становится инструкцией для реализации.

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
  вспомогательным и техническим экранам:
  1. Import review — главный review flow.
  2. Account detail — просмотр движений по счету.
  3. Manual operations — создание и редактирование ручных операций.
  4. Categories / Rules / Properties / Users / Workspace operations —
     вспомогательные CRUD/workspace функции. К этому моменту должен появиться
     явный reusable шаблон, который можно применить без ручного изобретения
     каждой страницы.
  5. Reports — финансовые итоги и таблицы.
  6. Mapping — настройка колонок импорта.
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
src/app/features/imports/presentation/mapping.py
src/app/features/imports/presentation/review/
```

`presentation/review/` является владельцем page context, `ReviewItemVM`,
action policy, labels, panels, reference lookup and state/confirmability
presentation rules.

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
```

Где:

- `page.py` содержит page-level context/builder.
- `item.py` содержит `ImportReviewPresenter` and item orchestration.
- `models.py` содержит маленькие VM dataclasses.
- `actions.py`, `panels.py`, `labels.py`, `references.py`, `state.py`
  держат отдельные presentation reasons to change.

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
- `css_classes`: `review-item`, `review-status-*`, `review-item-next`,
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

## Logic To Move Out Of Jinja

Из `src/app/templates/imports/_review_item.html` нужно постепенно перенести в
presenter:

- поиск `rule_suggestion` в `row.raw_payload`;
- определение `rule_auto_applied`;
- выбор `row_balance_problems`;
- open/error/name state диалога категории;
- выбор `selected_category_id`;
- поиск предложенной категории и объекта через циклы по `categories` и
  `properties`;
- вычисление первой строки очереди / `review-item-next`;
- вычисление route для linked operation: from/to entry;
- построение summary для transfer/non-transfer linked operation;
- определение ветки UI по `row.status.value`, `linked_operation_id`,
  `suggested_by_rule_id`;
- решение, какая кнопка primary/secondary/danger;
- сбор technical details.

В `src/app/templates/imports/review.html` позже можно вынести page-level логику:

- вычисление `latest_attempt`;
- `validation`;
- `review_queue`;
- workflow step state.

Но это не часть первого `Review item + action system` slice.

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

## Template Refactor Strategy

Новый review item partial должен стать стандартным компонентом:

```text
src/app/templates/imports/_review_item.html
```

Первый безопасный подход:

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
review-actions
review-actions__primary
review-actions__secondary
review-actions__menu
review-actions__danger
```

Правила:

- Новые review partials используют BEM-like classes.
- Старую верстку не трогать без необходимости.
- Для текущего stabilized slice допустим root modifier `review-item--vm` и
  старые внутренние классы `review-main` / `review-meta` как compatibility
  layer.
- При следующем UI touch point не смешивать старые классы `review-main` /
  `review-meta` с новым `review-item__*` внутри одного изменяемого блока.
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
    - `review-panel__*`;
    - `review-actions__*`.
    Root нового item помечен как `review-item--vm`. Старые CSS-классы
    `review-main`, `review-meta`, `review-topline` пока остаются как
    совместимость и будут мигрировать только при следующем UI touch point.
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
| 18 | Closed | Date is in the top line via `review-date-chip`; covered by template assertions around `review-topline`. |
| 19 | Closed | Row index is small meta; raw id is not surfaced as primary content; technical details do not compete with money/date/description in the current item layout. |
| 20 | Accepted debt | Stabilized new parts use `review-panel__*`, `review-actions__*`, and `review-item--vm`. Older inner classes (`review-main`, `review-meta`, `review-topline`) remain as an explicit compatibility layer until the next UI touch point. |
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

Новый CSS для panel/action слоя мигрирует к BEM-like naming постепенно:

- `review-panel__*`;
- `review-actions__*`.

Старые классы `review-main`, `review-meta`, `review-topline` и соседние
review-item классы будут мигрировать только при следующем естественном UI/refactor
touch point, чтобы не делать массовый rename без продуктовой пользы.

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

## Temporary Review Item Flag

Для внедрения нового review item используется временный template flag:

```text
use_review_item_vm=True
```

Цель: дать возможность быстро переключаться между старым
`RawTransaction`-based partial и новым `ReviewItemVM`-based partial без
DB-миграций, изменения URL endpoints и отката бизнес-логики.

Правила:

- Старый partial продолжает получать `row` / `RawTransaction`.
- Новый partial получает только `item` / `ReviewItemVM`.
- Не смешивать `row` и `item` внутри нового partial.
- Новый partial не должен обращаться напрямую к `RawTransaction`.

Пример:

```jinja
{% if use_review_item_vm %}
  {% include "imports/review/_item.html" with item=review_item_vm %}
{% else %}
  {% include "imports/_old_review_item.html" with row=row %}
{% endif %}
```

Флаг временный. После стабилизации нового review item:

1. Обновить тесты.
2. Проверить HTMX actions.
3. Удалить старый partial.
4. Удалить `use_review_item_vm`.
5. Оставить только `ReviewItemVM`-based rendering.

Не оставлять две ветки навсегда и не развивать старый partial дальше.

Текущий implementation slice выполнил этот пункт: `use_review_item_vm` и
старый `RawTransaction`-based review partial удалены, active review rendering
идет через `imports/review/_item.html` и подготовленный `ReviewItemVM`.

## Открытые вопросы

1. С какого первого implementation шага начинать: presenter/tests или template
   skeleton?

## Черновой список будущих тем

- Приоритетные экраны.
- Канонический financial row.
- Действия по статусам.
- Что должно быть таблицей, карточкой или detail view.
- Границы изменений в backend, routers, presenters, templates и CSS.
- ViewModel/API strategy для будущей миграции frontend.
- Acceptance criteria.
