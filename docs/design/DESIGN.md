# Booker Tee Design

Статус: активный UI/UX contract.

Архитектура React/API находится в
[`REACT_FRONTEND_DESIGN.md`](REACT_FRONTEND_DESIGN.md), формы — в
[`FORM_DESIGN.md`](FORM_DESIGN.md). Этот файл отвечает за пользовательское и
визуальное поведение.

## Направление

```text
modern financial workbench
dark-first
calm
dense
precise
trustworthy
with restrained rebellious creativity
```

Интерфейс должен ощущаться рабочим инструментом, а не marketing dashboard.
Выразительность создают типографика, ритм, ясные money/status signals и
небольшие акценты, а не декоративный шум.

## Основные принципы

1. Money и outcome заметнее технических деталей.
2. Одна страница имеет одну главную задачу.
3. Progressive disclosure скрывает сложность, но не последствия.
4. Status передаётся текстом и структурой, не только цветом.
5. Primary action один; destructive/rare actions отделены.
6. Server uncertainty показывается честно.
7. Dense не означает тесный или мелкий.
8. Mobile сохраняет workflow, а не просто сжимает desktop.

## App shell

- Постоянная навигация к dashboard, accounts, imports, manual ledger, reports и
  reference/admin sections.
- Активный пункт различим без цвета.
- Workspace context видим.
- Mobile navigation остаётся keyboard- и touch-доступной.
- Canonical ссылки ведут в React только после replacement gate.

## Working page

Рекомендуемая иерархия:

```text
PageHeader
  title + context
  status/summary
  primary action

working controls
  filters/form/progress

primary content
  rows/cards/table

secondary details
  validation/history/debug
```

Primary action не должен теряться внутри длинного technical/debug content.

## Money

- Использовать tabular numerals.
- Показывать currency рядом с amount или однозначно задавать её контекстом.
- Знак и направление не заменяются цветом.
- Income/expense/transfer tones семантические и theme-independent.
- Transfer показывает source и destination; его нельзя визуально выдавать за
  прибыль.
- Formatting не меняет Decimal value и не выполняет конвертацию.

## Repeated financial row

Строка отвечает на четыре вопроса:

1. Что произошло?
2. Когда?
3. Сколько и в каком направлении?
4. Что можно сделать дальше?

Desktop может использовать compact grid. Mobile перестраивает контент:

```text
identity/status
description
money/outcome
metadata
actions
expandable editor/details
```

Row identity и anchors стабильны. Открытая panel привязана к конкретной
entity/row; после mutation UI получает authoritative snapshot.

## Status and feedback

- `StatusLabel` — важный lifecycle state.
- `Badge` — compact status/count.
- `Tag` — secondary attribute/filter.
- Success/error feedback размещается рядом с изменённой сущностью.
- Created/updated entity может кратко подсвечиваться, но animation уважает
  `prefers-reduced-motion`.
- Blocking state содержит причину и следующий шаг.

## Actions

Иерархия:

```text
primary       — основной безопасный следующий шаг
secondary     — частое обратимое действие
quiet         — раскрытие/навигация
danger        — destructive или финансово значимое действие
```

- Не показывать ряд одинаково громких кнопок.
- Icon-only action имеет accessible name и достаточную hit area.
- Danger требует явного confirmation, если результат трудно восстановить.
- Disabled state объясняет причину; скрытие используется только при отсутствии
  права даже знать о возможности.

## Forms

- Label всегда видим.
- Required, help и error связаны с control.
- Server errors сохраняют draft.
- First invalid field получает focus после error summary.
- Submit pending предотвращает случайный double-submit.
- Money/date/account/category controls используют domain-specific labels.
- Полная композиция описана в [`FORM_DESIGN.md`](FORM_DESIGN.md).

## Technical details

Raw payload, parse history, IDs и diagnostics:

- secondary по иерархии;
- раскрываются явно;
- не включают secrets/storage paths;
- большие данные загружаются lazy и ограничиваются;
- чувствительные значения маскируются;
- не вытесняют action, который решает пользовательскую проблему.

## Responsive geometry

Поддерживаемые audit widths:

```text
desktop 1440
tablet   920
mobile   390
```

Обязательные свойства:

- нет horizontal page overflow;
- form controls не обрезаются;
- touch targets доступны;
- tables получают card/scroll strategy на уровне компонента;
- sticky/fixed элементы не закрывают focus и errors;
- длинные filenames/descriptions безопасно переносятся.

## Accessibility

- Semantic headings, landmarks, lists и tables.
- Keyboard доступ ко всем действиям.
- Видимый focus.
- Dialog возвращает focus trigger.
- Disclosure сообщает expanded state.
- Status/error не зависят только от цвета.
- Loading сообщает busy state.
- Contrast обеспечивается semantic tokens для каждой темы.

## Tokens and themes

Три уровня:

```text
primitive -> semantic -> component
```

Feature CSS использует semantic variables. Нельзя импортировать legacy global
CSS в React или кодировать Catppuccin palette прямо в component module.

Текущие темы:

- Catppuccin Mocha;
- Catppuccin Latte;
- test theme для проверки semantic contract.

Geometry не должна неожиданно меняться между темами.

## Shared vs feature UI

Shared candidates уже доказаны кодом:

- Button/IconButton;
- Badge/Tag/StatusLabel;
- MoneyValue;
- Field/Fieldset/FormError;
- PageFrame/PageHeader/RouteStatePage/RouteLoadingPage;
- RequestState;
- ConfirmationDialog;
- ExpansionPanel;
- WorkbenchSurface/WorkbenchHeader;
- WorkbenchToolbar/WorkbenchSearch;
- WorkbenchFilterRegion/WorkbenchStatus/WorkbenchContent;
- AppliedFilterSummary;
- ResponsiveRecordCollection;
- WorkbenchRow/WorkbenchPanel;
- ActionStack;
- SearchableSelect.

Feature владеет финансовым смыслом композиции. Shared component не импортирует
feature API и не знает, как подтвердить import row.

## UI verification

Для изменённого workflow:

- component/interaction tests;
- keyboard/focus check;
- realistic browser scenario;
- desktop/tablet/mobile screenshots;
- no console/page/request errors;
- explicit review отличий от baseline.

Temporary audit reports не становятся постоянными source-of-truth документами.
