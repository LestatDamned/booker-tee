# Workbench Row Design

Status: approved specification for incremental implementation.

## 1. Цель

`WorkbenchRow` — единый UI-контракт для повторяющихся строк рабочего интерфейса
Booker Tee:

- import review item;
- manual operation;
- account movement;
- category;
- property;
- transaction rule.

Рефакторинг должен уменьшить количество повторяющегося production-кода и
число мест, которые нужно менять для одного UI-решения. Абсолютное количество
строк во всем репозитории не является целевой метрикой: явные ViewModel и тесты
могут увеличить общий объем кода, если при этом уменьшаются дублирование и
связность.

## 2. Не цели

В рамках этого рефакторинга не создаются:

- единый универсальный `WorkbenchRowVM` для всех feature;
- универсальный CRUD-компонент;
- универсальный генератор форм;
- Jinja-шаблон с большим количеством `show_*` и `is_*` флагов;
- новая frontend-инфраструктура или SPA;
- полная копия поведения без JavaScript для сложного `reviewPanelDeck`;
- полный проект по аудиту WCAG 2.2 AA;
- browser/screenshot test infrastructure.

## 3. Способ композиции

Выбран общий контракт и небольшие shared-компоненты. Каждая feature владеет
своим шаблоном строки и собирает его из стандартных областей:

```text
WorkbenchRow
├── Main
│   ├── Header
│   ├── Description
│   ├── Meta
│   └── Signals
├── Aside
│   ├── Outcome
│   └── Actions
└── Expansion
```

Целевые CSS-классы:

```text
workbench-row
workbench-row__main
workbench-row__header
workbench-row__title
workbench-row__value
workbench-row__description
workbench-row__meta
workbench-row__signals
workbench-row__aside
workbench-row__outcome
workbench-row__actions
workbench-row__expansion
```

Пример feature-owned шаблона:

```jinja
<article id="{{ row.id }}" class="workbench-row manual-operation-row">
  <div class="workbench-row__main">
    ...
  </div>
  <aside class="workbench-row__aside">
    ...
  </aside>
  <div class="workbench-row__expansion">
    ...
  </div>
</article>
```

Небольшое повторение каркаса в feature-шаблонах допустимо. Не имитировать в
Jinja сложную систему именованных slots.

## 4. CSS-архитектура, BEM и темы

### 4.1 Отделение нового CSS от legacy

Новый CSS не добавляется в существующий монолитный `app.css`. В начале
миграции текущий файл переносится в `legacy.css`, а `app.css` становится только
точкой входа, которая явно задает порядок CSS-слоев.

Целевая структура:

```text
src/app/static/css/
├── app.css                         # entry point, только imports/layers
├── legacy.css                      # текущий app.css, временный legacy
├── foundation/
│   ├── tokens.css                  # spacing, type, radius, motion, contracts
│   └── base.css                    # новый минимальный global/base layer
├── themes/
│   └── catppuccin-mocha.css        # текущая тема через semantic tokens
├── components/
│   ├── workbench-row.css
│   ├── money-value.css
│   ├── action-stack.css
│   └── expansion-panel.css
└── features/
    └── import-review.css            # только imports-owned отклонения
```

Правила legacy-слоя:

- новый `WorkbenchRow` CSS в `legacy.css` не добавляется;
- в legacy допустимы только обязательные исправления и удаления при миграции;
- compatibility selectors помечаются как временные;
- после переноса последнего потребителя `legacy.css` и его import удаляются;
- порядок cascade/layers должен позволять новому компонентному CSS
  предсказуемо переопределять legacy без роста `!important`;
- версия CSS asset должна учитывать изменения импортируемых файлов, а не
  только mtime entry point `app.css`.

Допускается использовать CSS cascade layers:

```text
legacy -> tokens -> base -> components -> features -> utilities
```

Если layers не используются на первом шаге, тот же порядок обеспечивается
порядком imports. Не смешивать layered и unlayered application styles без
проверки их cascade priority.

### 4.2 BEM-соглашение

Новые компоненты используют BEM:

```text
Block      .workbench-row
Element    .workbench-row__main
Modifier   .workbench-row--working

Block      .money-value
Element    .money-value__currency
Modifier   .money-value--income
```

Правила:

1. Block описывает самостоятельный UI-компонент.
2. Element принадлежит одному block и записывается через `__`.
3. Modifier описывает вариант или состояние и записывается через `--`.
4. Не создавать цепочки вида `.block__element__child`.
5. Modifier не используется без базового block/element class.
6. Feature может использовать BEM mix:

   ```html
   <article class="workbench-row manual-operation-row">
   ```

7. Feature-класс добавляется только при реальном feature-specific оформлении.
8. Для component CSS не использовать ID selectors и tag-qualified selectors.
9. Предпочитать один class selector; глубокие descendant selectors допускаются
   только для явной связи состояния с элементом.
10. Не повышать specificity через повторение классов.
11. `!important` запрещен, кроме документированных инфраструктурных случаев,
    например `[x-cloak]`.
12. Общие layout utilities допускаются только как небольшой документированный
    набор и не должны скрывать обязательную структуру компонента.

CSS-класс может быть публичным selector общего поведения, как
`.workbench-row`. `data-*` используется только для значения или конфигурации
поведения, а не как дубликат BEM-класса.

### 4.3 Токенизация

Компоненты используют semantic tokens, а не конкретные цвета палитры:

```text
--color-bg-canvas
--color-bg-surface
--color-bg-elevated
--color-text-primary
--color-text-secondary
--color-border-default
--color-border-strong
--color-focus-ring
--color-accent
--color-status-success
--color-status-warning
--color-status-danger
--color-money-income
--color-money-expense
--color-money-transfer
--color-money-profit
--color-money-adjustment
```

Foundation tokens также могут описывать повторяющиеся шкалы:

```text
--space-*
--radius-*
--font-family-*
--font-size-*
--duration-*
--z-index-*
```

Не токенизировать каждое одноразовое CSS-значение. Токен вводится, если
значение повторяется, имеет семантический смысл или должно меняться между
темами.

Raw palette values (`#...`, `rgb(...)`) разрешены в theme files. Component и
feature files используют semantic tokens и производные `color-mix()` от них.

На время миграции допускаются compatibility aliases старых переменных:

```css
--bg: var(--color-bg-canvas);
--surface: var(--color-bg-surface);
--text: var(--color-text-primary);
```

После удаления legacy-потребителей aliases удаляются.

### 4.4 Готовность к темам

Текущая палитра оформляется как первая явная тема `catppuccin-mocha`, а не как
набор цветов, зашитый в компоненты.

Theme contract:

```html
<html data-theme="catppuccin-mocha">
```

```css
:root,
[data-theme="catppuccin-mocha"] {
  color-scheme: dark;
  --color-bg-canvas: #11111b;
  --color-text-primary: #cdd6f4;
  --color-accent: #89b4fa;
  /* полный semantic token contract */
}
```

Будущая тема, например Catppuccin Latte или другая палитра, должна добавляться
новым theme file и переопределением того же semantic token contract. Изменять
`workbench-row.css`, `money-value.css` и другие component files для добавления
темы не требуется.

В этот рефакторинг входит подготовка theme contract и тема
`catppuccin-mocha`. UI-переключатель тем и хранение пользовательского выбора
не входят в scope и могут быть реализованы позже. При добавлении темы отдельно
проверяются контраст финансовых состояний, focus ring, disabled и error states.

## 5. Владение компонентами

Shared UI:

```text
MoneyValue
StatusBadge
MetaItem
OutcomeCard
Action
ActionStack
ActionMenu
RequestIndicator
RequestError
FormError
FieldError
RetryAction
ExpansionPanel
EditPanel
```

Feature-owned UI:

```text
ReviewItem
ManualOperationRow
AccountMovementRow
CategoryRow
PropertyRow
TransactionRuleRow
ReviewPanelDeck
CategoryPanel
TransferPanel
```

Каждая feature самостоятельно определяет:

- ViewModel строки;
- доменные значения и feature-specific состояния;
- action policy;
- содержимое и валидацию форм;
- feature-specific HTMX/OOB semantics;
- workspace и permission checks.

## 6. ActionStack

Правая панель имеет общий каркас:

```text
ActionStack
├── Primary
├── Secondary
├── More
│   └── Danger zone
└── Technical
```

Presenter/ActionPolicy feature распределяет готовые действия по группам:

```text
primary_action
secondary_actions
menu_actions
danger_actions
technical_info
```

`ActionStack` только отображает группы. Он не определяет permissions,
допустимость перехода состояния или бизнес-приоритет действия.

Правила отображения:

- основное действие заметно и расположено первым;
- обычные вторичные действия следуют за ним;
- редкие действия находятся в `More`;
- destructive actions находятся в отдельной `Danger zone`;
- техническая информация расположена внизу и не конкурирует с действиями.

Существующий `ActionVM` и `ui/_action.html` используются как основа, если их
контракт подходит без feature-specific бизнес-условий в шаблоне.

## 7. Отображение денег

### 7.1 Источник финансового смысла

`MoneyValue` — единый presentation-компонент для денежных значений в
Workbench Row, таблицах, отчетах, KPI и других экранах.

Источник финансового смысла остается на сервере:

```text
Operation
  -> использовать готовый OperationType;

Balance / profit / aggregate
  -> feature Presenter передает positive / negative / neutral / profit;

Raw transaction до подтверждения
  -> серверный resolver/presenter передает временную визуальную семантику.
```

Jinja, JavaScript и Alpine не определяют тип операции по знаку суммы.
Положительная проводка перевода не становится доходом.

Для operation-owned значений отдельный дублирующий `MoneyTone` не нужен:
визуальный ключ берется из `OperationType.value`. Для баланса, прибыли и других
не-operation значений Presenter передает готовый display tone.

### 7.2 Форматирование

Общий серверный `MoneyFormatter` подготавливает `MoneyValueVM`:

```python
MoneyValueVM(
    amount_label="15 000,00",
    currency_label="RUB",
    tone="income",
)
```

Стандартный визуальный формат:

```text
15 000,00 RUB
-744,94 RUB
0,00 RUB
```

Правила:

- пробел между разрядами;
- две цифры после запятой;
- код валюты отображается отдельным элементом;
- знак передает подготовленное сервером значение;
- формат полей ввода и машинного экспорта может отличаться.

Целевой CSS-контракт:

```text
money-value
money-value__amount
money-value__currency
money-value--income
money-value--expense
money-value--transfer
money-value--adjustment
money-value--profit
money-value--positive
money-value--negative
money-value--neutral
```

Row-level tone, например цвет левой границы, является отдельным оформлением и
не участвует в финансовых расчетах.

## 8. Disclosure и edit panel

Общий Alpine-контроллер `disclosure` управляет только открытием и закрытием
области.

Lazy edit panel является композицией:

```text
disclosure + HTMX lazy loading
```

Он не является отдельным Alpine-контроллером:

- Alpine управляет видимостью;
- HTMX загружает и заменяет HTML;
- feature владеет формой, валидацией и сохранением.

Стандартный жизненный цикл:

```text
Первое открытие
  -> HTMX загружает форму.

Закрытие и повторное открытие
  -> используется уже загруженная форма.

Ошибка валидации
  -> сервер возвращает строку с открытой панелью и ошибками.

Успешное сохранение
  -> сервер возвращает обновленную строку с закрытой панелью.

Обновление строки другим действием
  -> панель по умолчанию закрыта.
```

Presenter передает начальное состояние `edit_panel_open`. Alpine не хранит
финансовые данные и не определяет доступность действия.

`reviewPanelDeck` остается imports-owned контроллером для нескольких взаимно
исключающих review panels, lazy loading, OOB и validation state.

## 9. Состояния строки

Состояния разделяются по визуальным каналам:

```text
Финансовый тип
  -> MoneyValue и необязательный row-level tone.

Inactive
  -> прозрачность и доступность действий.

Feature status / error / next
  -> badge, signal или feature-owned отметка.

Target / recent / working
  -> временная подсветка, фон или outline.
```

Приоритет временной подсветки:

```text
working > target > recent
```

Финансовый тип и feature status не исчезают из-за временной подсветки.

Кандидат на единое поведение:

```text
target
  URL hash указывает на стабильный id строки. Браузер прокручивает к строке,
  CSS использует `.workbench-row:target`.

recent
  Feature Presenter добавляет `.workbench-row--recent` на основании
  временного query parameter или другого серверного контекста.

working
  Обычный JavaScript добавляет `.workbench-row--working` во время работы и
  восстанавливает класс после HTMX replacement.
```

`.workbench-row` является корнем компонента и стабильным JavaScript selector.
`data-workbench-row` не вводится, поскольку он не несет отдельного значения и
дублирует класс. `data-*` используется только для реальных данных или настроек
поведения.

Feature-owned состояния остаются feature-owned:

```text
review-item--next
review-item--status-*
manual-operation-row--*
account-movement-row--*
```

Scroll restoration и сложное OOB-поведение остаются у соответствующей feature.

## 10. HTML id и anchors

Корневая строка использует стабильный entity-prefixed id:

```text
operation-{uuid}
property-{uuid}
category-{uuid}
rule-{uuid}
review-item-{uuid}
```

Внутренние id образуются от корневого:

```text
operation-{uuid}-edit-panel
operation-{uuid}-edit-form
operation-{uuid}-edit-toggle
```

Presenter подготавливает все id. Jinja не склеивает их самостоятельно.

Этот id является публичным UI-контрактом для:

- URL hash;
- HTMX `target` и `select`;
- `aria-controls` и `aria-labelledby`;
- JavaScript поведения.

Изменение CSS-классов не должно изменять стабильный id сущности.

## 11. HTMX response contract

Один application-сценарий поддерживает обычное SSR-представление и HTMX:

```text
Обычный запрос
  -> redirect или полная SSR-страница.

HTMX-запрос
  -> минимальный стабильный fragment.
```

Стандартные виды ответа:

```text
loadPanel
  -> содержимое edit panel;

replaceSelf
  -> целая WorkbenchRow;

replaceList
  -> контейнер списка;

oobUpdate
  -> основная строка и feature-owned OOB-фрагменты.
```

Ошибка валидации формы возвращает строку с открытой панелью. Успешное
сохранение возвращает обновленную строку с закрытой панелью.

`oobUpdate` не является обязательным shared-поведением и используется только
там, где одно действие действительно обновляет дополнительные области.

## 12. Loading и errors

Состояния отображаются локально, рядом со строкой или панелью, в которой было
выполнено действие.

Стандарт:

```text
Начало запроса
  -> действие получает aria-busy="true";
  -> повторное нажатие временно блокируется;
  -> панель показывает RequestIndicator.

Ошибка валидации
  -> сервер возвращает открытую форму;
  -> FieldError отображается рядом с полем;
  -> FormError использует role="alert".

Сетевая ошибка или 5xx
  -> существующая строка не удаляется;
  -> локальный RequestError объясняет проблему;
  -> RetryAction позволяет повторить запрос.

Успех
  -> fragment заменяется;
  -> используется working/recent feedback;
  -> обязательный toast не показывается.
```

Глобальные уведомления используются только для событий уровня всей страницы.

## 13. Accessibility

Обязательный базовый контракт:

1. Действия реализуются через `button` или `a`, а не кликабельный `div`.
2. Переключатель панели имеет `aria-controls` и `aria-expanded`.
3. Панель имеет стабильный `id` и понятный заголовок.
4. Загрузка сообщает `aria-busy="true"`.
5. Общая ошибка формы использует `role="alert"`.
6. Ошибка поля связана с input через `aria-describedby`.
7. После ошибки фокус переходит на первое ошибочное поле.
8. Статус не обозначается только цветом.
9. Все действия доступны с клавиатуры.
10. Видимый focus не отключается.
11. Анимации учитывают `prefers-reduced-motion`.

После успешного HTMX replacement фокус возвращается к основному действию
обновленной строки или к управляемому focus target строки.

## 14. Progressive enhancement

Основные финансовые и CRUD-сценарии имеют обычный HTTP fallback:

- открыть сущность;
- открыть форму редактирования;
- отправить форму;
- выполнить основное действие;
- увидеть ошибки валидации;
- вернуться к измененной строке.

HTMX и Alpine улучшают этот сценарий, но не являются единственным способом
выполнить основное действие.

Дополнительные удобства могут зависеть от JavaScript:

- мгновенное переключение review panels;
- сохранение scroll position;
- временная подсветка `working`;
- OOB-обновление нескольких областей.

## 15. Permissions и workspace boundary

Проверки выполняются на двух уровнях.

Presentation-уровень:

```text
Permissions + состояние сущности
  -> ActionPolicy
  -> подготовленные группы ActionStack.
```

Server-уровень при каждом запросе:

```text
1. Определить текущий workspace.
2. Найти сущность только внутри workspace.
3. Проверить permission.
4. Проверить допустимость перехода состояния.
5. Выполнить действие.
```

Скрытая кнопка не является защитой endpoint. Jinja только отображает результат
ActionPolicy и не вычисляет permissions самостоятельно.

UX-правила:

- действие без разрешения обычно не показывается;
- readonly-состояние объясняется отдельным status;
- временно невозможное действие ActionPolicy скрывает либо сопровождает
  понятным объяснением.

## 16. Responsive contract

Используется один HTML-шаблон с responsive reflow.

Основной существующий breakpoint сохраняется на `920px` до проверки пилота:

```text
Шире 920px
  -> Main и Aside расположены рядом;
  -> Expansion занимает полную ширину снизу.

920px и уже
  -> Main, Aside и Expansion расположены друг под другом;
  -> боковая граница Aside заменяется верхней.
```

Дополнительные правила:

- сумма и заголовок могут переноситься, но не перекрываются;
- длинный текст использует `overflow-wrap`;
- основные действия на телефоне занимают доступную ширину;
- минимальная высота интерактивного элемента около `44px`;
- edit panel не создает горизонтальную прокрутку;
- feature сама определяет компактное отображение своих сложных таблиц.

## 17. Тесты рефакторинга

Все новые тесты этого UI-рефакторинга создаются в:

```text
tests/ui_refactor/
```

Во время рефакторинга они проверяют:

- adoption нового контракта;
- MoneyFormatter и MoneyValueVM;
- Presenter и ActionPolicy;
- стабильные id и accessibility-связи;
- обычные и HTMX HTTP-ответы;
- открытое состояние после ошибки;
- закрытое состояние после успешного сохранения;
- permissions и workspace isolation;
- временную legacy-совместимость.

Не фиксировать точный полный HTML, порядок всех CSS-классов, конкретные
отступы и другие быстро меняющиеся детали реализации.

После завершения рефакторинга владелец проекта отдельно решает, какие тесты из
`tests/ui_refactor/` удалить, оставить или перенести. Агент не удаляет их
автоматически.

Существующие template-тесты пересматриваются во время миграции: полезные
адаптируются, а проверки удаленного legacy-контракта не должны заставлять
сохранять старую реализацию. Набор тестов не оставляется в заведомо красном
состоянии.

Ручной visual checklist выполняется для каждой мигрированной feature:

```text
desktop;
920px;
mobile;
открытая панель;
ошибка формы;
working / target / recent;
readonly mode.
```

## 18. Миграция

### Этап 1. Baseline

- создать минимальные проверки в `tests/ui_refactor/`;
- зафиксировать целевые экраны;
- составить список старых классов, JS-поведений и дублирующихся блоков;
- зафиксировать baseline production-кода в затронутом scope.

### Этап 2. Минимальная shared-основа

- перенести текущий монолитный CSS в `legacy.css`;
- превратить `app.css` в явный CSS entry point;
- создать foundation tokens и тему `catppuccin-mocha`;
- базовый CSS-контракт `WorkbenchRow`;
- `MoneyFormatter`, `MoneyValueVM`, `MoneyValue`;
- `ActionStack` поверх существующего `ActionVM`;
- общий `disclosure`;
- HTMX response contracts и локальные request states;
- временные compatibility-классы только там, где они нужны миграции.

### Этап 3. Первый пилот: manual operation

Проверить на одном полном сценарии:

- деньги;
- description/meta;
- ActionStack;
- lazy edit panel;
- validation и save lifecycle;
- HTMX replacement;
- обычный HTTP fallback;
- technical details;
- состояния строки.

### Этап 4. Второй пилот: account movement

Проверить переиспользование компонентов при другой точке зрения на сумму и
источник операции.

### Этап 5. Контрольная точка

До дальнейшей миграции оценить:

- уменьшилось ли дублирование production-кода;
- не появился ли универсальный шаблон с флагами;
- не дублируются ли старое и новое поведение;
- подходят ли `ActionStack`, `MoneyValue` и disclosure двум feature;
- удобен ли breakpoint `920px`;
- какие части контракта нужно скорректировать.

### Этап 6. Простые entity rows

Перенести последовательно:

1. properties;
2. transaction rules;
3. categories.

### Этап 7. Import review

Перенести последним. Не переносить в shared UI:

- `reviewPanelDeck`;
- workflow state `next`;
- scroll restoration;
- сложные OOB-обновления;
- review-specific panels и validation semantics.

### Этап 8. Feedback

Унифицировать `target`, `recent`, `working` и удалить в мигрированном scope:

```text
data-entity-working
entity-card--working
feature-specific recent/target JavaScript selectors
```

### Этап 9. Cleanup

- удалить compatibility-классы после миграции всех потребителей;
- удалить `legacy.css` и compatibility token aliases;
- удалить неиспользуемые CSS-селекторы;
- удалить дублирующиеся Alpine/JavaScript-контроллеры;
- удалить замененные partials;
- обновить документацию;
- сравнить production-код с baseline;
- оставить решение по судьбе `tests/ui_refactor/` владельцу проекта.

Legacy-классы не удаляются до template, interaction и visual checks.

Основное соответствие на время миграции:

| Текущий класс | Целевой класс |
| --- | --- |
| `financial-row` | `workbench-row` |
| `financial-row__main` | `workbench-row__main` |
| `financial-row__topline` | `workbench-row__header` |
| `financial-row__side` | `workbench-row__aside` |
| `financial-row__result-card` | `outcome-card` |
| `financial-row__drawer` | `workbench-row__expansion` |
| `row-drawer` | `expansion-panel` |

Пример временной совместимости:

```html
<article class="workbench-row financial-row manual-operation-row">
```

## 19. Definition of Done

Рефакторинг завершен, когда:

1. Все шесть целевых экранов используют контракт `WorkbenchRow`.
2. Не создан единый Jinja-монолит или универсальный `WorkbenchRowVM`.
3. Денежные значения используют серверный финансовый смысл и формат
   `15 000,00 RUB`.
4. Jinja, Alpine и JavaScript не определяют финансовый тип по знаку суммы.
5. Панели действий используют общий `ActionStack`, а состав определяет
   feature ActionPolicy.
6. Обычные edit panels используют общий disclosure и согласованный lifecycle.
7. `reviewPanelDeck` остается imports-owned.
8. HTMX и обычный HTTP работают по согласованному response contract.
9. Стабильные id соответствуют `{entity}-{uuid}-...`.
10. `working`, `target`, `recent` унифицированы.
11. Выполнен accessibility и responsive contract.
12. Новый CSS следует BEM-соглашению и находится вне legacy-слоя.
13. Компоненты используют semantic tokens, а Catppuccin Mocha оформлена как
    отдельная тема без palette values в component files.
14. Удалены `legacy.css`, compatibility selectors и token aliases без
    оставшихся потребителей.
15. В затронутом production-коде уменьшено дублирование; необъяснимый рост
    production-кода считается поводом для повторного ревью.
16. Проверки в `tests/ui_refactor/` и актуальные существующие тесты проходят.
17. Выполнен ручной visual checklist на desktop, `920px` и mobile.
