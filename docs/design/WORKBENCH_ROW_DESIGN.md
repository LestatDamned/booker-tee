# Проектирование Workbench Row

Статус: утвержденная дочерняя спецификация Frontend Next; shared foundation и
list/edit-срез первого пилота manual operation реализованы 17 июля 2026 года.

Родительская стратегия: [`FRONTEND_NEXT_DESIGN.md`](FRONTEND_NEXT_DESIGN.md).

`WorkbenchRow` создается внутри изолированного нового фронтенда. Он не использует
общий CSS cascade, базовый шаблон или presentation partials текущего фронтенда.

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
- новый frontend-фреймворк или SPA;
- полная копия поведения без JavaScript для сложного `reviewPanelDeck`;
- полный проект по аудиту WCAG 2.2 AA;
- новая отдельная browser/screenshot test infrastructure; используется
  существующий `scripts/ui_audit.py`.

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

Новый CSS не добавляется в существующий монолитный `static/css/app.css` и не
загружается вместе с ним в Next frontend. Текущий файл остается замороженным
presentation asset старого frontend до удаления его последнего потребителя.
Next использует собственный base template и собственную точку входа CSS.

Целевая структура нового изолированного web-adapter:

```text
src/app/
├── static/css/app.css              # current frontend, frozen legacy asset
└── web/static/css/
    ├── app.css                     # Next entry point
    ├── settings/
    │   └── tokens.css
    ├── foundation/
    │   └── base.css
    ├── themes/
    │   └── catppuccin-mocha.css
    ├── components/
    │   ├── ui-button.css
    │   ├── ui-badge.css
    │   ├── ui-field.css
    │   ├── request-state.css
    │   ├── workbench-row.css
    │   ├── money-value.css
    │   ├── action-stack.css
    │   └── expansion-panel.css
    └── features/
        └── import-review.css
```

Правила изоляции:

- Next base template не подключает current `static/css/app.css`;
- current frontend не подключает Next CSS до переключения workflow;
- новые компоненты не используют current CSS-классы и partials;
- в current CSS допустимы только критические исправления и удаления при
  миграции;
- каждый мигрированный Workbench-компонент должен перестать зависеть от
  legacy-селекторов строк;
- feature-specific current selectors удаляются после cutover workflow;
- shared current selectors удаляются после последнего current-потребителя;
- полное удаление current `static/css/app.css` не входит в Definition of Done
  одного `WorkbenchRow`, но входит в завершение миграции всего frontend;
- версия Next CSS asset учитывает изменения импортируемых файлов, а не только
  mtime Next entry point.

Допускается использовать CSS cascade layers:

```text
tokens -> base -> components -> features -> utilities
```

Если layers не используются на первом шаге, тот же порядок обеспечивается
порядком imports. Legacy не является слоем Next cascade.

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

Compatibility aliases current CSS-переменных в Next не создаются. Первая тема
сразу определяет новый semantic token contract; необходимые значения current
палитры переносятся в theme file как значения, а не как зависимость от current
CSS.

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

### 5.1 Граница ViewModel и Jinja

Целевая цепочка нового frontend:

```text
Application DTO / read projection
  -> feature Presenter
  -> неизменяемая feature ViewModel
  -> Jinja
```

Jinja не получает ORM-модели и не обращается к repositories, persistence
relationships или workspace membership. Presenter заранее подготавливает:

- видимые пользователю тексты и подписи;
- форматированные денежные значения;
- стабильные HTML-ID и внутренние URL;
- badges, статусы и понятные ошибки;
- `ActionSetVM` уже с учетом permissions и action policy.

В шаблоне допустимы только presentation-операции: вывести поле, проверить
наличие optional UI-блока и перебрать подготовленную коллекцию. Шаблон не
вычисляет финансовый тип, разрешение или lifecycle transition.

ViewModel создаются для устойчивых UI-концептов и границ компонентов. Не
создавать отдельный dataclass для каждого wrapper или декоративного `div`.
Обычные неструктурированные словари не являются основным контрактом нового
frontend.

## 6. ActionStack

Правая панель имеет общий каркас:

```text
ActionStack
├── Primary
├── Secondary
├── More
│   └── Danger zone
```

Расположение действий задает `ActionSetVM` и является единственным источником
истины:

```text
primary: ActionVM | None
secondary: tuple[ActionVM, ...]
menu: tuple[ActionVM, ...]
danger: tuple[ActionVM, ...]
```

`ActionVM` описывает само действие, но не содержит `placement`. Feature
Presenter/ActionPolicy сразу помещает действие в нужную группу `ActionSetVM`.
Дополнительная группировка в Jinja или `ActionStack` не выполняется.

`ActionStack` только отображает группы. Он не определяет permissions,
допустимость перехода состояния или бизнес-приоритет действия.

Правила отображения:

- основное действие заметно и расположено первым;
- обычные вторичные действия следуют за ним;
- редкие действия находятся в `More`;
- destructive actions находятся в отдельной `Danger zone`;
- группа `primary` содержит не больше одного действия;
- отдельной группы `technical` нет.

Новые `ActionVM`, `ActionSetVM` и renderer создаются внутри Frontend Next с
нуля. Существующие `ActionVM` и `ui/_action.html` используются только как
источник найденных сценариев; новый frontend не зависит от их контракта или
разметки.

### 6.1 Типы действий

`ActionVM` является объединением трех явных presentation-типов:

```python
ActionVM = LinkActionVM | SubmitActionVM | DisclosureActionVM
```

Минимальные контракты:

```text
LinkActionVM
  -> label, url, icon;

SubmitActionVM
  -> label, url, method, icon, confirmation;

DisclosureActionVM
  -> label, fallback_url, load_url, panel_id, icon.
```

Каждый тип имеет собственный неизменяемый dataclass и discriminator `kind` для
явной ветки renderer. Не использовать один dataclass с набором несвязанных
optional-полей: link без `url`, disclosure без `panel_id` и другие недопустимые
состояния должны быть невозможны при создании ViewModel.

Общие presentation-свойства могут повторяться в трех небольших dataclass либо
собираться через маленький value object. Не вводить иерархию наследования или
универсальный builder только ради устранения нескольких строк.

`disabled` и понятная `disabled_reason` являются состоянием доступного действия,
а не отдельным типом. `readonly` не является действием: если пользователю нечего
выполнять, интерфейс показывает отдельное понятное status/empty state.

`DisclosureActionVM.fallback_url` обязателен: без HTMX действие открывает
полноценную SSR-форму. `SubmitActionVM` рендерится как обычная HTML-форма, которую
HTMX только улучшает. Renderer выбирает разметку по `kind`, но не содержит
permission или бизнес-условий.

### 6.2 Технические детали

`ActionStack` и строка не показывают внутренние UUID, database keys,
debug-состояния и отдельный блок технической информации. Не выводить «ID
операции», «ID строки» и аналогичные значения как обычный пользовательский
контент.

Стабильные идентификаторы продолжают использоваться невидимо в HTML, URL и
HTMX-контрактах. Финансовая прослеживаемость оформляется понятными действиями:

```text
Открыть операцию
Открыть исходный документ
Открыть строку импорта
```

Пользователь видит смысл и источник данных, но не внутреннее устройство
системы.

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

Для движения по конкретному счету сервер передает две независимые оси:

```text
operation_type  -> income / expense / transfer;
entry_direction -> inflow / outflow относительно выбранного счета.
```

Пример внутреннего перевода:

```text
исходящая проводка -> transfer + outflow;
входящая проводка  -> transfer + inflow.
```

`EntryDirection` описывает только направление `MoneyEntry` и не заменяет
`OperationType`. `inflow` не означает `income`, а `outflow` не означает
`expense`. Оба значения вычисляются или подготавливаются на сервере; frontend
их не выводит из знака суммы.

Для строки всей операции `entry_direction` может отсутствовать. Для баланса,
прибыли и других не-operation значений Presenter передает отдельный готовый
display tone `positive / negative / neutral / profit`.

### 7.2 Форматирование

Общий серверный `MoneyFormatter` подготавливает `MoneyValueVM`:

```python
MoneyValueVM(
    amount_label="15 000,00",
    currency_label="RUB",
    operation_type="transfer",
    entry_direction="inflow",
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
money-value--inflow
money-value--outflow
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
  -> форма скрывается, но загруженный HTML и несохраненный draft остаются в DOM;
  -> повторное открытие показывает тот же draft.

Отмена
  -> draft сбрасывается к последним серверным значениям;
  -> панель закрывается без mutation-запроса.

Ошибка валидации
  -> сервер возвращает строку с открытой панелью и ошибками.

Успешное сохранение
  -> сервер возвращает обновленную строку с закрытой панелью.

Обновление строки другим действием
  -> панель по умолчанию закрыта.
```

Панели принадлежат отдельным строкам и не образуют глобальный accordion:
пользователь может открыть несколько edit panels одновременно. Открытие одной
строки не закрывает другую и не требует глобального JavaScript draft store.
Формы загружаются лениво, поэтому закрытые ни разу не открытые строки не
увеличивают HTML страницы тяжелой form-разметкой.

`aria-controls` переключателя указывает на стабильный container панели, а
`hx-target` lazy-load — на отдельный content container внутри нее. HTMX не
заменяет header панели и действие «Закрыть», поэтому панель остается управляемой
во время загрузки и после нее.

Сброс по кнопке «Отмена» выполняется локальным presentation-поведением формы.
После внешнего `replaceRow` старый draft удаляется вместе с замененной строкой.
Если Alpine перенес локальный proxy со старого root при `outerHTML`, общий
settle-helper переинициализирует только помеченный disclosure и восстанавливает
серверное закрытое состояние. Зависший loading placeholder после успешного
save недопустим.

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

Стандартное единое поведение:

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

Корневой `row_id` идентифицирует отображаемую запись, а не обязательно главную
бизнес-сущность страницы. Он строится по стабильному первичному идентификатору
записи:

```text
manual operation   -> operation-{operation_id}
account movement   -> money-entry-{money_entry_id}
import review item -> raw-transaction-{raw_transaction_id}
property           -> property-{property_id}
category           -> category-{category_id}
transaction rule   -> rule-{rule_id}
```

Не использовать индекс строки и не собирать суррогатные комбинации вида
`operation-{operation_id}-account-{account_id}`. Одна `Operation` может иметь
несколько `MoneyEntry`, поэтому ID операции не гарантирует уникальность строки
движения по счету.

Ссылка на связанную бизнес-сущность хранится в ViewModel отдельно от `row_id`:

```text
row_id        -> money-entry-{money_entry_id}
operation_url -> /operations/{operation_id}
```

Если внешний переход задает бизнес-сущность, серверный row locator находит
соответствующую отображаемую запись и формирует окончательный URL hash. Jinja и
JavaScript не угадывают эту связь.

### 10.1 Закрепленная целевая строка

URL hash не считается достаточной гарантией: целевая запись может отсутствовать
на текущей странице или не соответствовать фильтру. Серверный Presenter получает
страничный результат и отдельную optional `pinned_target`:

```text
page_items: tuple[RowVM, ...]
pinned_target: RowVM | None
```

Правила:

- row locator загружает цель только внутри текущей workspace boundary;
- если цель уже есть в `page_items`, отдельная закрепленная копия не создается;
- отсутствующая цель временно показывается над обычным списком;
- `pinned_target` не изменяет pagination count и не учитывается дважды;
- несовпадение с фильтром или страницей объясняется коротким пользовательским
  сообщением;
- target-контекст одноразовый и не переносится автоматически в обычные ссылки
  pagination;
- после разрешения проекции hash указывает на фактический `row_id`, например
  `money-entry-{money_entry_id}`.

Примеры сообщения:

```text
Показана выбранная операция вне текущей страницы.
Показана выбранная операция вне текущего фильтра.
```

Frontend не сбрасывает фильтры и не вычисляет номер страницы только ради
targeted feedback.

Внутренние id образуются от корневого:

```text
{row_id}-edit-panel
{row_id}-edit-form
{row_id}-edit-toggle
```

Presenter подготавливает все id. Jinja не склеивает их самостоятельно.

Этот id является публичным UI-контрактом для:

- URL hash;
- HTMX `target` и `select`;
- `aria-controls` и `aria-labelledby`;
- JavaScript поведения.

Изменение CSS-классов не должно изменять стабильный id сущности.
Стабильный id не выводится как видимый текст и не создает отдельного блока
технической информации.

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

replaceRow
  -> целая WorkbenchRow;

removeRow
  -> строка удаляется из текущего списка;

replaceList
  -> контейнер списка;

oobUpdate
  -> основной fragment и feature-owned OOB-фрагменты.
```

Область ответа выбирает feature presentation-router по результату операции и
контексту текущего списка. `WorkbenchRow`, HTMX и клиентский JavaScript не
вычисляют ее самостоятельно.

Матрица выбора:

| Результат действия | HTMX-ответ |
| --- | --- |
| Изменилось только содержимое строки | `replaceRow` |
| Строка больше не соответствует текущему фильтру | `removeRow` |
| Изменились состав списка, pagination или empty state | `replaceList` |
| Изменились счетчики или другие feature-owned области | основной ответ + `oobUpdate` |
| Обычный HTTP-запрос | redirect с безопасным контекстом списка |

Примеры:

```text
изменить описание операции в списке all -> replaceRow;
архивировать property в списке active -> removeRow;
удалить последнюю строку страницы -> replaceList;
изменить данные, влияющие на счетчик -> replaceRow/replaceList + oobUpdate.
```

Mutation-запрос должен передавать достаточный серверный контекст фильтра и
pagination, чтобы renderer мог выбрать правильный ответ. `return_to` или
аналогичный URL проверяется как внутренний безопасный путь и не используется
для открытого redirect.

Ошибка валидации формы возвращает строку с открытой панелью. Успешное
сохранение возвращает обновленную строку с закрытой панелью.

### 11.1 HTTP-статус ошибки валидации

Ошибка пользовательского ввода возвращает `422 Unprocessable Content` для
обычного и HTMX-запроса:

```text
обычный HTTP -> 422 + полная SSR-страница с ошибками;
HTMX         -> 422 + локальный HTML-fragment с ошибками.
```

Новый frontend регистрирует один глобальный обработчик:

```javascript
document.addEventListener("htmx:beforeSwap", (event) => {
  if ([409, 422].includes(event.detail.xhr.status)) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});
```

Обработчик применяется только к ожидаемым `422` и `409`. Authorization errors,
not-found и `5xx` не заменяют строку или форму через этот контракт.
Feature-router не возвращает фиктивный `200` для ошибки валидации или конфликта.

### 11.2 Optimistic concurrency

Редактируемые Workbench-сущности получают integer `version`. Presenter передает
его форме как невидимый технический token, а mutation command возвращает его в
application layer:

```html
<input type="hidden" name="version" value="4">
```

Repository выполняет атомарный update по `workspace_id + id + version` и после
успеха увеличивает версию. Проверка версии отдельным предварительным `SELECT` без
условия в `UPDATE` недостаточна, потому что оставляет race condition.

Если версия устарела:

```text
HTTP 409 Conflict;
запись не изменяется;
форма сохраняет введенные значения и показывает локальное объяснение;
пользователь может загрузить актуальную версию или отменить свои изменения.
```

На первом этапе не строить diff двух версий и не вводить pessimistic edit lock.
Необходимые model fields и Alembic migrations добавляются вместе с миграцией
соответствующего workflow, а не одной неподтвержденной массовой схемой.

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
  -> панель показывает RequestIndicator;
  -> конкурирующий mutation-запрос той же формы или строки не запускается.

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

### 12.1 Синхронизация и повторная отправка

HTMX-запросы синхронизируются локально на ближайшей форме или
`.workbench-row` через согласованный `hx-sync` contract. Независимые строки не
блокируют друг друга; глобальный request manager не создается.

UI-защита включает:

```text
disabled на submit/action во время запроса;
aria-busy="true";
локальный RequestIndicator;
запрет параллельных конфликтующих mutations одной строки.
```

Disabled-кнопка не является финансовой гарантией. Для каждого workflow отдельно
проверяется риск повторной доставки:

```text
create / confirm / post / transfer
  -> при возможности второго финансового результата нужен server-side
     idempotency token или существующая равнозначная гарантия;

cancel / restore / archive / update
  -> транзакция, workspace boundary и проверка допустимого состояния.
```

Не добавлять idempotency-инфраструктуру механически ко всем GET, lazy panel и
безопасным повторяемым запросам.

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

После `removeRow` общий focus helper использует детерминированный порядок:

```text
1. Основное действие следующей строки.
2. Основное действие предыдущей строки.
3. Заголовок списка.
4. Empty state, если список стал пустым.
```

После `replaceList` helper сначала ищет прежний `row_id`; если строки больше
нет, применяется тот же порядок. Положение строки и активное действие
запоминаются до HTMX swap, а фокус восстанавливается после settle.

Фоновое обновление не перехватывает фокус, если активный элемент находился вне
заменяемого fragment. Общий helper управляет только DOM-контекстом и не знает
feature или бизнес-правила.

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

### 16.1 Поддерживаемые браузеры

Целевые browser engines нового frontend:

```text
актуальные Chromium-based browsers;
актуальный Firefox;
актуальный Safari.
```

Устаревшие браузеры, Internet Explorer и старые WebView не входят в scope.
Каждый workflow проходит автоматический Chromium UI audit на desktop, `920px`
и mobile viewport. Firefox проверяется на контрольных этапах, Safari — когда
доступна подходящая среда.

Не использовать экспериментальный browser API без fallback. Современные CSS-
возможности допустимы, но отсутствие необязательного эффекта не должно скрывать
финансовое значение, статус, focus state или действие. Основной HTTP-сценарий
остается доступен без JavaScript согласно progressive enhancement contract.

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
- изоляцию от current frontend;
- `422` validation и `409` conflict responses;
- optimistic concurrency и защиту критичных mutations;
- pinned target и восстановление фокуса.

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

### 17.1 Легкий quality gate

Перед переключением canonical URL workflow должен пройти:

1. Presenter/ViewModel contract tests.
2. Обычные HTTP и HTMX response tests.
3. Permission и workspace isolation tests.
4. Актуальные financial/domain tests.
5. Релевантный сценарий существующего Chromium `ui_audit.py`.
6. Ручной visual checklist.
7. Сравнение с performance baseline.

Не фиксировать полную HTML-разметку, pixel-perfect screenshots каждого
состояния и каждый CSS modifier отдельным E2E-тестом.

Baseline первого пилота включает:

```text
database queries без нового N+1;
HTML size репрезентативного списка;
отсутствие eager edit forms в закрытых строках;
размер нового CSS и количество feature-specific дубликатов;
отсутствие глобального controller/listener на каждую строку.
```

Сначала фиксируются реальные показатели manual ledger. Произвольные числовые
лимиты заранее не задаются; необъяснимое ухудшение следующего workflow требует
повторного design review.

## 18. Миграция

### Этап 1. Baseline

- создать минимальные проверки в `tests/ui_refactor/`;
- зафиксировать целевые экраны;
- составить список старых классов, JS-поведений и дублирующихся блоков;
- зафиксировать baseline production-кода в затронутом scope;
- зафиксировать queries, HTML size и CSS size первого репрезентативного списка;
- выбрать релевантный сценарий существующего `ui_audit.py`;
- добавить в существующий UI audit контрольный viewport `920px`, не создавая
  отдельную browser-инфраструктуру.

### Этап 2. Минимальная shared-основа

- создать изолированные Next base template, static root и CSS entry point;
- не подключать current `static/css/app.css` в Next;
- создать foundation tokens и тему `catppuccin-mocha`;
- создать ограниченный foundation: `UIButton`, `UIBadge`, `UIField` и
  `RequestState`;
- базовый CSS-контракт `WorkbenchRow`;
- `MoneyFormatter`, `MoneyValueVM`, `MoneyValue`;
- новые `ActionVM`, `ActionSetVM` и `ActionStack`;
- общий `disclosure`;
- HTMX response contracts и локальные request states;
- не использовать compatibility-классы current frontend внутри Next.

### Этап 3. Первый пилот: manual operation

Проверить на одном полном сценарии:

- деньги;
- description/meta;
- ActionStack;
- lazy edit panel;
- validation и save lifecycle;
- HTMX replacement;
- обычный HTTP fallback;
- пользовательскую прослеживаемость без блока технических деталей;
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

- переключить canonical workflow URL на Next;
- удалить current feature templates, presenters и response renderers без
  оставшихся потребителей;
- удалить из current `static/css/app.css` селекторы строк без потребителей;
- оставить shared current selectors только при наличии других потребителей;
- удалить неиспользуемые CSS-селекторы в мигрированном scope;
- удалить дублирующиеся Alpine/JavaScript-контроллеры;
- удалить замененные partials;
- обновить документацию;
- сравнить production-код с baseline;
- оставить решение по судьбе `tests/ui_refactor/` владельцу проекта.

Current frontend-классы не удаляются до template, interaction и visual checks
Next workflow.

Концептуальное соответствие для инвентаризации, а не для одновременного
использования классов в Next:

| Текущий класс | Целевой класс |
| --- | --- |
| `financial-row` | `workbench-row` |
| `financial-row__main` | `workbench-row__main` |
| `financial-row__topline` | `workbench-row__header` |
| `financial-row__side` | `workbench-row__aside` |
| `financial-row__result-card` | `outcome-card` |
| `financial-row__drawer` | `workbench-row__expansion` |
| `row-drawer` | `expansion-panel` |

Такой compatibility mix в Next запрещен:

```html
<article class="workbench-row financial-row manual-operation-row">
```

## 19. Definition of Done

Рефакторинг завершен, когда:

1. Все шесть целевых экранов используют контракт `WorkbenchRow`.
2. Не создан единый Jinja-монолит или универсальный `WorkbenchRowVM`; Jinja
   получает явные ViewModel без ORM-моделей.
3. Денежные значения используют серверный финансовый смысл и формат
   `15 000,00 RUB`.
4. Jinja, Alpine и JavaScript не определяют финансовый тип по знаку суммы.
5. Панели действий используют общий `ActionStack`, `ActionSetVM` и три явных
   типа действий, а состав определяет feature ActionPolicy.
6. Обычные edit panels используют общий disclosure и согласованный lifecycle.
7. `reviewPanelDeck` остается imports-owned.
8. HTMX и обычный HTTP работают по согласованному response contract.
9. Стабильный `row_id` идентифицирует отображаемую запись; ссылки на связанные
   бизнес-сущности хранятся отдельно.
10. `working`, `target`, `recent` и server-pinned target унифицированы.
11. Выполнены accessibility, deterministic focus и responsive contracts.
12. Новый CSS следует BEM-соглашению и находится вне legacy-слоя.
13. Компоненты используют semantic tokens, а Catppuccin Mocha оформлена как
    отдельная тема без palette values в component files.
14. Все мигрированные Workbench-компоненты изолированы от current templates,
    CSS и JavaScript. После cutover удалены feature-specific current selectors
    и presentation-код без оставшихся потребителей. Полное удаление current
    `static/css/app.css` не является условием завершения одной спецификации
    `WorkbenchRow`.
15. В затронутом production-коде уменьшено дублирование; необъяснимый рост
    production-кода считается поводом для повторного ревью.
16. Проверки в `tests/ui_refactor/` и актуальные существующие тесты проходят.
17. Выполнены существующий Chromium UI audit и ручной visual checklist на
    desktop, `920px` и mobile.
18. Для первого пилота зафиксирован performance baseline; следующие workflows
    не ухудшают его без объясненной причины.
19. Validation и conflict responses используют согласованные `422` и `409`.
20. Optimistic concurrency предотвращает незаметный stale overwrite.
21. Critical financial mutations проверены на повторную отправку и
    idempotency-риск.
22. В обычном UI не показываются внутренние UUID и блоки технических деталей.
