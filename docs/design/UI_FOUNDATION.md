# React UI Foundation

Статус: практический каталог и decision guide для React UI.

Этот документ отвечает на вопрос: **что переиспользовать и как собрать новую
страницу без нового локального варианта уже решённой задачи**.

- Общие визуальные и interaction-принципы находятся в
  [`DESIGN.md`](DESIGN.md).
- Подробный контракт форм находится в [`FORM_DESIGN.md`](FORM_DESIGN.md).
- TypeScript API и фактическое поведение компонента определяются его кодом в
  [`frontend/app/ui`](../../frontend/app/ui) и тестами.
- Визуальные состояния проверяются на `/app/foundation`.

Документ не дублирует props каждого компонента. Он фиксирует устойчивую
семантику, композицию и границу владения CSS.

## Перед началом страницы

Используйте этот порядок до создания JSX или CSS:

1. Найдите подходящую ответственность в [`frontend/app/ui`](../../frontend/app/ui).
2. Откройте `/app/foundation` и проверьте компонент в Mocha, Latte и test theme.
3. Найдите уже мигрированный feature с похожим **workflow**, а не только похожим
   внешним видом.
4. Соберите страницу из shared-компонентов и оставьте feature только её
   финансовый смысл, данные и уникальную раскладку.
5. Создавайте новый shared-компонент лишь после появления устойчивого
   повторяющегося контракта.

```text
Нужная ответственность уже есть?
  да  -> переиспользовать shared component
  нет -> одинаков ли смысл и поведение минимум в нескольких местах?
           да  -> выделить узкий shared component и добавить в foundation
           нет -> оставить реализацию внутри feature
```

Внешнее сходство само по себе не доказывает возможность переиспользования.
Например, две строки могут иметь одинаковую рамку, но разные финансовые
инварианты и действия.

## Слои UI и CSS

```text
primitive tokens
  spacing / radius / typography / duration / z-index
        ↓
semantic theme tokens
  surface / text / border / action / status / money / focus
        ↓
shared component CSS Modules
  control states / common geometry / accessibility behavior
        ↓
feature composition CSS Modules
  columns / hierarchy / domain-specific layout
```

### Tokens

- Геометрические primitives находятся в
  [`tokens.css`](../../frontend/app/styles/tokens.css).
- Semantic colors назначаются темами в
  [`styles/themes`](../../frontend/app/styles/themes).
- Component CSS использует semantic variables. Raw palette и hex-цвета в
  component или feature module не добавляются.
- Тема меняет цветовой смысл, но не должна неожиданно менять геометрию.
- Новый token получает имя по назначению, а не по текущему оттенку.

### Shared CSS владеет

- одинаковыми высотой, padding, radius и состояниями одного компонента;
- hover, active, disabled, pending и focus-visible;
- общей адаптивной геометрией компонента;
- семантическим отображением status, feedback и money tone.

### Feature CSS владеет

- колонками и приоритетами конкретной финансовой записи;
- уникальной композицией workflow;
- локальной раскладкой данных, которая не повторяется как устойчивый контракт;
- осмысленной desktop-only раскладкой для специализированных инструментов.

Feature не импортирует CSS другого feature и не переопределяет внутренние
селекторы shared-компонента. Legacy global CSS не импортируется в React.

## Каталог компонентов

### Действия и навигация

| Компонент                                  | Использовать                                                                                                 | Не использовать                                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| `Button`, `ButtonLink`, `RouterButtonLink` | Текстовое действие или ссылка с общей иерархией `primary`, `secondary`, `ghost`, `dangerSecondary`, `danger` | Для кликабельного контейнера записи или локальной копии стилей кнопки |
| `IconButton`                               | Компактное знакомое действие с обязательным accessible name                                                  | Когда пользователю нужен текст для понимания действия                 |
| `ActionStack`                              | Устойчивая раскладка primary, secondary, danger и overflow-действий; `orientation="row"` даёт компактный `•••` trigger не меньше 44×44 px | Для бизнес-правил доступности действий                                |
| `BackLink`                                 | Предсказуемый возврат из detail/workflow                                                                     | Как замену истории браузера без явного destination                    |
| `SelectionTabs`                            | Переключение соседних выборок: например, активные и архивные; активный tab всегда различим не только цветом  | Для пошагового процесса или запуска mutation                          |

На экране одна главная CTA. Остальные действия визуально подчинены ей. Иконки
берутся из общего `Icon`; emoji и случайные SVG-наборы не используются.

В тесной строке или карточке видимым остаётся одно наиболее частое
недеструктивное действие. Навигационные, lifecycle и destructive команды
группируются в overflow `ActionStack`, причём dangerous group остаётся
визуально отделённой. Набор полноразмерных кнопок не превращается в высокую
вертикальную колонку только из-за нехватки ширины.

### Значения и состояния

| Компонент     | Семантика                                                                                  |
| ------------- | ------------------------------------------------------------------------------------------ |
| `MoneyValue`  | Сумма с currency, tabular numerals и финансовым tone; форматирование не вычисляет значение |
| `StatusLabel` | Lifecycle, validation или workflow state, важный для следующего решения                    |
| `Badge`       | Короткий count рядом с подписью; accessible label объясняет число                          |
| `Tag`         | Классификация, атрибут или применённый фильтр, не lifecycle state                          |

Быстрый выбор:

```text
Это состояние сущности или проверки? -> StatusLabel
Это количество?                       -> Badge
Это категория, тип или атрибут?       -> Tag
Это денежное значение?                -> MoneyValue
```

Цвет не является единственным носителем значения: остаются текст, знак суммы,
label или icon.

### Структура страницы и workbench

| Компонент                    | Ответственность                                                    |
| ---------------------------- | ------------------------------------------------------------------ |
| `PageFrame`                  | Основная ширина и вертикальный ритм страницы                       |
| `PageHeader`                 | Eyebrow, title, description и page-level action                    |
| `WorkbenchSurface`           | Единая рамка рабочего реестра                                      |
| `WorkbenchHeader`            | Верхняя зона workbench; обычно содержит `PageHeader`               |
| `WorkbenchToolbar`           | Поиск, tabs, фильтры и create action                               |
| `WorkbenchSearch`            | Постоянно доступный поиск с явной submit-семантикой                |
| `WorkbenchFilterRegion`      | Раскрываемая область draft-фильтров под toolbar                    |
| `WorkbenchStatus`            | Result count или локальное состояние коллекции                     |
| `WorkbenchContent`           | Основное содержимое внутри workbench                               |
| `ResponsiveRecordCollection` | Desktop table + mobile record list с одной семантикой данных       |
| `WorkbenchRow`               | Общая геометрия финансовой строки и её action/expansion zones      |
| `WorkbenchPagination`        | Range, page size и навигация страниц в нижней границе реестра      |
| `WorkbenchEmptyState`        | Первичная пустота или отсутствие результатов после фильтрации      |
| `AppliedFilterSummary`       | Читаемый applied state и единый сброс фильтров                     |
| `DocumentWorkbenchHeader`    | Заголовок сложного document/review workflow с контекстом документа |

`ResponsiveRecordCollection` владеет переключением desktop/mobile и базовой
оболочкой. Feature по-прежнему владеет колонками, фактами, статусами и
действиями конкретной сущности.

### Формы и раскрытие

| Компонент                  | Использовать                                                                                   |
| -------------------------- | ---------------------------------------------------------------------------------------------- |
| `Field`, `Fieldset`        | Видимые label/legend, hint, required и inline error вокруг native control                      |
| `FormGrid`, `FormGridItem` | Общая responsive-раскладка полей без изменения DOM order                                       |
| `FormActions`              | Cancel слева, submit справа; обе кнопки имеют видимую границу и общую геометрию                |
| `FormError`                | Ошибка одного control рядом с ним                                                              |
| `FormErrorSummary`         | Несколько ошибок с переходом к полям и focus на первую invalid control                         |
| `SearchableSelect`         | Длинный справочник, который пользователь узнаёт по названию и должен искать, например category |
| `WorkbenchPanel`           | Создание новой сущности справа, пока реестр остаётся видимым                                   |
| `ExpansionPanel`           | Исправление существующей сущности непосредственно под её строкой                               |
| `ConfirmationDialog`       | Отдельное труднообратимое или destructive действие                                             |

Контейнер выбирается по контексту сущности:

```text
Новая сущность       -> WorkbenchPanel справа
Существующая сущность -> ExpansionPanel под её строкой
Destructive решение   -> ConfirmationDialog
```

В раскрытой области находится только форма. Повторный page header, описание
workflow и декоративные карточки внутрь неё не добавляются. При закрытии focus
возвращается к trigger. Если форма имеет несохранённый важный draft, случайное
закрытие должно быть предотвращено или подтверждено.

### Loading, errors и feedback

| Ситуация                                          | Компонент                                           |
| ------------------------------------------------- | --------------------------------------------------- |
| Весь route загружается                            | `RouteLoadingPage`                                  |
| Route недоступен, не найден или сломан            | `RouteStatePage`                                    |
| Локальная часть уже открытой страницы загружается | `RequestState`                                      |
| Ошибка поля                                       | `FormError`                                         |
| Ошибки нескольких полей                           | `FormErrorSummary`                                  |
| Сбой действия или recoverable request             | `InlineNotice` рядом с контекстом и recovery action |
| Успешная явная mutation                           | `ToastViewport` через `useToastQueue`               |
| Pending mutation                                  | Spinner и disabled state внутри вызвавшей её кнопки |

Toast не перехватывает focus, объявляется как polite live status и кратко
подтверждает создание, сохранение, перенос состояния или удаление. Локальная
надпись `Сохранено` в строку сущности не добавляется. Промежуточный выбор внутри
review form подтверждается обновлением самой формы, без отдельного Toast.

## Рецепты страниц

### Реестр / collection workbench

```text
AppShell
└─ PageFrame
   └─ WorkbenchSurface
      ├─ WorkbenchHeader
      │  └─ PageHeader
      ├─ WorkbenchToolbar
      │  ├─ WorkbenchSearch
      │  ├─ SelectionTabs
      │  ├─ filters trigger
      │  └─ create action
      ├─ WorkbenchFilterRegion (по требованию)
      ├─ AppliedFilterSummary (если есть applied filters)
      ├─ WorkbenchContent
      │  └─ ResponsiveRecordCollection / WorkbenchRow
      └─ WorkbenchPagination

create -> WorkbenchPanel справа
edit   -> ExpansionPanel под выбранной row
```

Search остаётся видимым. Structured filters изменяют локальный draft;
`Применить` записывает normalized state в URL и сбрасывает страницу на первую.
Tabs, фильтры, pagination и back navigation сохраняют предсказуемое URL-state.

### Detail / review workflow

```text
PageFrame
├─ BackLink
├─ DocumentWorkbenchHeader или PageHeader
├─ primary workflow state/action
├─ рабочие строки или sections
└─ secondary diagnostics в progressive disclosure
```

Technical payload, IDs и parser diagnostics не конкурируют с решением, ради
которого открыта страница.

## Когда не унифицировать

Не нужен универсальный `Table`, `Form`, `Card` или schema renderer только ради
одинакового внешнего вида. Shared abstraction оправдана, если совпадают:

1. пользовательский смысл;
2. interaction и accessibility contract;
3. responsive behavior;
4. состояния и причины изменения.

Feature остаётся владельцем финансовых инвариантов, API DTO, mutation policy,
permission logic и содержания строк. Shared UI не знает, как подтвердить import
row, вычислить balance или определить transfer direction.

Mapping остаётся специализированным desktop-heavy инструментом. Он обязан
использовать общие controls, tokens и feedback, но может сохранять уникальную
рабочую геометрию, если responsive-компромисс ухудшает основную задачу.

## Добавление shared-компонента

Новый компонент в `frontend/app/ui` должен:

1. иметь узкую устойчивую ответственность и не импортировать feature;
2. использовать semantic tokens и собственный CSS Module;
3. поддерживать keyboard, focus-visible, accessible name/state и корректный DOM
   order;
4. иметь pending/disabled/error states, если они входят в его контракт;
5. сохранять доступную hit area около 44 px для самостоятельного действия;
6. работать в Mocha, Latte и test theme без изменения геометрии;
7. получить component/interaction test;
8. получить репрезентативный пример на `/app/foundation`;
9. быть добавлен в этот каталог, если меняется правило выбора.

## Проверка новой или перенесённой страницы

- [ ] Найден и изучен похожий workflow, а не только похожий screenshot.
- [ ] Проверены `frontend/app/ui` и `/app/foundation`.
- [ ] Shared-компоненты не дублируются локальным JSX/CSS.
- [ ] Raw palette/hex и cross-feature CSS imports отсутствуют.
- [ ] Видимы selected, hover, active, focus, disabled и pending states.
- [ ] Tabs имеют одинаковую подсветку активного состояния и `aria-current` или
      `aria-selected` по семантике.
- [ ] Labels видимы; errors находятся рядом с controls; recovery понятен.
- [ ] Keyboard order совпадает с визуальным; dialog/panel возвращает focus.
- [ ] Touch actions имеют достаточную hit area и не зависят от hover.
- [ ] Проверены 1440, 920 и 390 px; отсутствует page-level horizontal overflow.
- [ ] Проверены Mocha и Latte; функциональный цвет не является единственным
      сигналом.
- [ ] Запущены relevant component tests, typecheck, build и Playwright scenario.
