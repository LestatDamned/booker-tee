# Transaction Rules UX/UI audit

Статус: SSR source/interaction audit completed 2026-08-01. Authenticated browser
screenshots не создавались: существующий realistic audit регистрирует и мутирует
test data, а audit request не расширял authority на такую mutation. Geometry
ниже подтверждена templates, CSS и template tests; realistic screenshots входят
в implementation gate.

## Текущий пользовательский outcome

Страница помогает пользователю:

1. понять, зачем правила нужны Import Review;
2. увидеть активные/выключенные правила и их условие/результат;
3. найти правило по merchant/name/category/property;
4. отфильтровать по category/status;
5. создать rule вручную или загрузить набор defaults;
6. lazy-edit конкретную запись в контексте списка;
7. включить/выключить или удалить rule;
8. открыть конкретное rule по anchor из Categories.

Viewer видит rule meaning и status без mutation controls.

## Что уже работает хорошо

- Page copy объясняет rule на конкретном merchant example.
- Row отвечает на “условие → результат” и текстом показывает lifecycle state.
- Create defaults to safe `suggest`, а не silent ledger action.
- Advanced fields скрыты progressive disclosure.
- Edit form загружается lazy, поэтому list не размножает reference options.
- Search/category/status filters имеют URL state и reset.
- New rule получает feedback и stable anchor.
- Delete отделён в danger zone и подтверждается.
- Read-only user не получает misleading disabled mutation controls.
- CSS имеет 920/390 collapse strategy и переносит длинные patterns.

Эти outcomes нужно сохранить, но не legacy DOM/HTMX implementation.

## Findings по severity

### Critical

1. **`auto_apply` обещает больше, чем делает.** Label “автоприменение” можно
   прочитать как silent posting. Реальный contract — suggestion plus quick
   confirm после server confirmability. React copy обязана явно сказать, что
   операция не проводится без пользователя.
2. **Delete impact скрыт.** Copy говорит только о будущих выписках, хотя delete
   обнуляет direct provenance у существующих raw rows и может влиять на restored
   review state.
3. **Expected validation не сохраняет draft.** Legacy mutation converts errors
   to generic `400`; HTMX form не имеет field errors, summary и recovery
   contract. React/API нужны typed `422` и сохранение local draft.

### High

1. **Create defaults слишком широкие.** Комбинация `contains + any direction +
   expense` способна создать rule с неожиданным охватом. Operation type и
   direction должны быть осознанным выбором либо сопровождаться visible preview.
2. **Mode/condition preview отсутствует до submit.** Пользователь не видит
   итоговую фразу с direction/amount/property и не может оценить breadth.
3. **Hidden matching semantics.** Account/priority могут влиять на rule, но SSR
   row их не показывает; local data не использует их, production guard всё равно
   обязателен.
4. **Archived current targets теряются в edit picker.** Active-only options
   недостаточны для сохранения historical relation.
5. **No stale recovery.** Параллельные вкладки silently overwrite update/toggle
   или удаляют уже изменённую запись.
6. **Seeder confirmation неточен.** Оно обещает не менять user rules, но runtime
   меняет mode совпавшего rule.
7. **List architecture не масштабируется.** Все rules загружаются и фильтруются
   в Python; current 69 max не оправдывает будущий unbounded read.

### Medium

1. Create form находится в accordion над list; раскрытие сдвигает весь registry.
   UI Foundation уже определяет `WorkbenchPanel` для new entity.
2. Edit open/close построен на hidden `<summary>`, inline `onclick` и HTMX
   target. Focus return/unsaved draft confirmation не выражены как component
   contract.
3. Form controls не имеют inline error relation, error summary и focus-first-
   invalid behavior.
4. Amount inputs используют text + `inputmode=decimal`, но не задают min/step и
   не объясняют absolute amount semantics.
5. Create/edit submit buttons имеют 40px, advanced summary — 32px; это ниже
   project target около 44px для самостоятельного action.
6. На 920px filters и advanced form полностью становятся одной колонкой; для
   tablet это безопасно, но избыточно высоко и требует screenshot audit.
7. Status badge text корректен, но mode/direction/type собраны одной строкой без
   явного hierarchy; scanability ухудшается при property и amount range.
8. “Показать ещё” изменяет limit вместо настоящей страницы; Back/Forward не
   восстанавливает позицию внутри большой выборки однозначно.
9. Count labels имеют неверные русские формы.

## React information architecture

```text
AppShell
└─ PageFrame
   └─ WorkbenchSurface
      ├─ WorkbenchHeader
      │  └─ PageHeader
      │     ├─ title / outcome copy
      │     └─ secondary “Базовые правила”
      ├─ WorkbenchToolbar
      │  ├─ WorkbenchSearch
      │  ├─ SelectionTabs: Все / Активные / Выключенные
      │  ├─ category filter trigger
      │  └─ primary “Новое правило”
      ├─ WorkbenchFilterRegion
      │  └─ SearchableSelect category + apply/reset
      ├─ AppliedFilterSummary
      ├─ WorkbenchStatus
      ├─ WorkbenchContent
      │  └─ ResponsiveRecordCollection
      │     ├─ semantic desktop table
      │     └─ semantic mobile ordered list
      └─ WorkbenchPagination

create -> WorkbenchPanel
edit   -> ExpansionPanel under selected record
delete -> ConfirmationDialog
```

На странице одна primary CTA — “Новое правило”. Seeder является secondary rare
action и не конкурирует с creation.

## Rule row hierarchy

Desktop columns:

1. name plus pattern/match type;
2. scope: direction and optional absolute amount;
3. outcome: operation type, category, property;
4. mode and lifecycle status;
5. actions.

Mobile order:

```text
name + Active/Disabled StatusLabel
condition sentence
outcome sentence
scope/mode Tags
primary edit or read-only state
overflow lifecycle/delete
optional ExpansionPanel
```

Rule status uses `StatusLabel`; match type/direction/mode are `Tag`, not lifecycle
badges. Amount range is plain localized text, not `MoneyValue`, because currency
is absent and range compares absolute amount across a rule scope.

Anchor target `#rule-uuid` receives semantic target state and scroll margin, but
does not force edit open. After create, navigate/replace to the anchor, focus the
new row heading and show one polite Toast.

## Form composition

Primary reading order:

```text
WHEN
  match type + pattern
  visible preview of normalized condition

SCOPE
  direction
  optional absolute min/max

THEN SUGGEST
  operation type
  category
  property

BEHAVIOR
  suggest / quick-confirm eligible

DETAILS
  optional name
```

Recommendations:

- visible labels, `Field`/`Fieldset`, `FormGrid`, `FormActions`;
- `SearchableSelect` for category/property when lists are long;
- no placeholder-only meaning;
- preview states that “quick confirm” still requires explicit confirmation;
- validate on submit/blur, not every keystroke;
- server error summary links to fields and focuses first invalid control;
- create/edit preserve draft on `422` and expected network error;
- unsaved panel/row switch uses `ConfirmationDialog`;
- only one editor open; while editing, page navigation/create is disabled or
  explicitly confirmed;
- current archived target remains visible as “архив · текущее значение”, but
  cannot be newly selected.

## Shared component reuse

### UI Foundation

Use directly:

- `PageFrame`, `PageHeader`, `WorkbenchSurface/Header/Toolbar/Content/Status`;
- `WorkbenchSearch`, `WorkbenchFilterRegion`, `AppliedFilterSummary`;
- `SelectionTabs`, `ResponsiveRecordCollection`, `WorkbenchPagination`;
- `WorkbenchEmptyState`, `RequestState`, `InlineNotice`;
- `Button`, `RouterButtonLink`, `ActionStack`;
- `StatusLabel`, `Tag`;
- `WorkbenchPanel`, `ExpansionPanel`, `ConfirmationDialog`;
- `Field`, `Fieldset`, `FormGrid`, `FormActions`, `FormErrorSummary`;
- `SearchableSelect`, `ToastViewport`.

Do not add a universal Rule/Card/CRUD/form generator. A feature-local rule table,
mobile record and form remain clearer.

### Imports / Import Review

Reuse interaction contracts, not feature internals:

- rule mode copy must match Import Review quick-confirm semantics;
- authoritative snapshot reconciliation, pending button and `InlineNotice`
  recovery;
- rule creation from confirmation stays in Import Review application flow;
- cross-link becomes canonical `/rules` SPA route;
- do not import Import Review CSS/components into Transaction Rules.

### Properties

Reuse:

- collection + local committed snapshot pattern;
- create `WorkbenchPanel`, row `ExpansionPanel`, unsaved close confirmation;
- lifecycle pending/conflict reload/retry and Toast;
- active/current-archived reference presentation decision.

Do not copy Property lifecycle policy: rule disable is not Property archive.

### Categories

Reuse:

- URL search/view state and read-only capabilities;
- `ResponsiveRecordCollection`, `ActionStack`, stable query/hash links;
- server-owned blocker/capability facts;
- lifecycle blocker linking between Categories and filtered Rules.

Do not reuse Category DTO or infer rule capability from category counts.

## Loading, feedback and accessibility

- route load: `RouteLoadingPage`; route failure: `RouteStatePage`;
- local mutation failure: `InlineNotice` next to panel/row with retry/reload;
- mutation button owns spinner and disabled state;
- successful create/update/toggle/delete/seed: one polite Toast;
- `aria-current`/selected state for status tabs;
- table caption and scoped headers; mobile list has equivalent reading order;
- disclosure/dialog returns focus to its trigger;
- Delete dialog initial focus is Cancel;
- no status/mode conveyed by color alone;
- 44px action targets, visible focus, reduced motion;
- test Mocha, Latte and test theme at 1440, 920 and 390 without page overflow.

## Intentional visual differences from SSR

The following are recommended improvements, not regressions:

- create moves from accordion to right WorkbenchPanel;
- filters/list share one workbench boundary;
- mode label no longer says bare “автоприменение”;
- destructive actions use shared dialog instead of generic form confirm;
- true pagination replaces increasing server limit;
- error summary and inline field errors preserve draft;
- lifecycle state uses Foundation status/action hierarchy;
- legacy global CSS/JS and inline HTMX behavior are not copied.
