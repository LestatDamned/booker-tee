# Categories SSR UX/UI audit

Статус: observed baseline и target guidance, не implementation spec.

## Метод и baseline

Проверены templates, presenter/service contracts, category-specific global CSS,
shared legacy JS, tests и локальный authenticated Playwright scenario
`realistic`:

```bash
UV_CACHE_DIR=/tmp/booker-tee-uv-cache uv run python scripts/ui_audit.py \
  --authenticated --scenario realistic --path categories \
  --theme catppuccin-mocha \
  --output-dir /tmp/booker-tee-categories-ssr-mocha
```

Результат: 3/3 pages passed на 1440x1000, 920x900 и 390x844; HTTP 200,
horizontal overflow 0, console/page/request/UX assertion errors отсутствуют.
Screenshots временные и не входят в repository.

Дополнительно применён `ui-ux-pro-max`: directory/search pattern, высокая
информационная плотность, явное подтверждение destructive actions, visible
labels, submit feedback, keyboard focus и 375/768/1024/1440 acceptance.
Предложенные skill palette/font/style не используются: Booker Tee сохраняет
собственные semantic tokens, Mocha/Latte и UI Foundation.

## Что работает

- title/hint объясняют финансовый смысл category;
- active/archive/system/all доступны как URL views;
- system и archived status переданы текстом, не только цветом;
- name — явная identity, технический UUID скрыт;
- operation/rule counts ведут в detail/context;
- server errors сохраняют create/edit draft;
- read-only mode скрывает mutation controls;
- direct Reports return path валидируется против open redirect;
- responsive baseline не имеет horizontal overflow.

## Основные проблемы

### Information hierarchy и density

- realistic workspace показывает около 25 почти одинаковых full-width cards;
  desktop и особенно mobile превращаются в очень длинную страницу;
- каждая row повторяет крупную кнопку «Открыть категорию», хотя сама identity и
  counts уже являются навигацией;
- группировка создаёт повторяющиеся eyebrow «пользовательские» перед каждым kind;
- list не показывает total count/search и не помогает быстро найти category;
- `all` смешивает system/custom/archive и размывает lifecycle model;
- постоянный tutorial hint и create accordion отодвигают directory вниз;
- видимый summary `<details>` содержит одновременно «Открыть Закрыть» в
  rendered state;
- notes, kind, status и usage не образуют стабильных desktop columns.

### Actions и feedback

- row CTA визуально громче identity и повторяется десятки раз;
- create/edit используют native details без полного `aria-expanded`, focus
  return и dirty-draft contract;
- ошибки не связаны с fields через `aria-invalid`/`aria-describedby`, focus не
  переводится к first invalid field;
- archive выполняется сразу и не объясняет active-rule consequence;
- delete появляется по неполному dependency policy и использует browser confirm;
- нет pending/double-submit/stale conflict recovery;
- success feedback зависит от redirect/recent banner вместо локального
  committed-state feedback.

### Detail

- header, action stack, edit drawer, period strip, три KPI, unbounded operations
  table и rules cards создают несколько конкурирующих уровней;
- summary показывает все три money values даже для clearly income-only или
  expense-only category;
- operations table на mobile остаётся legacy responsive table contract;
- rules полностью дублируют часть будущего Rules workbench;
- отсутствует pagination, поэтому category history может сделать detail тяжёлым;
- action «в архив» не показывает, что category исчезнет из pickers, но active
  rules могут продолжить её назначать.

### Shell и adaptive behavior

- 920 px legacy nav переносится и увеличивает верхний chrome;
- 390 px menu/workspace/upload/header/tabs/hint/create занимают значительную
  часть first viewport;
- mobile full-width action в каждой card удваивает вертикальный ритм;
- SSR не использует React AppShell, Mocha/Latte parity и shared focus/dialog
  contracts.

## Целевая информационная иерархия

```text
/app/categories
└─ AppShell -> PageFrame -> WorkbenchSurface
   ├─ WorkbenchHeader / PageHeader: count, title, concise description, Reports
   ├─ WorkbenchToolbar
   │  ├─ WorkbenchSearch
   │  ├─ SelectionTabs: Active / Archive / System
   │  └─ primary "Новая категория"
   ├─ read-only / request notice
   ├─ WorkbenchContent
   │  ├─ WorkbenchEmptyState
   │  └─ ResponsiveRecordCollection
   │     └─ identity -> kind/status -> usage -> quiet open action
   ├─ WorkbenchPanel: create
   └─ ToastViewport

/app/categories/:categoryId
└─ AppShell -> PageFrame -> WorkbenchSurface
   ├─ WorkbenchHeader: back context, identity, kind/status, actions
   ├─ WorkbenchToolbar: search, filters and applied state
   ├─ server-owned compact money summary
   ├─ paginated semantic list / ReadOnlyFinancialRow: confirmed operations
   ├─ bounded linked-rules preview + "Все правила"
   ├─ ExpansionPanel: edit
   ├─ ConfirmationDialog: kind/lifecycle/delete impact
   └─ ToastViewport
```

Card/button wall заменяется record collection: desktop table даёт scan по
identity/kind/usage, mobile list сохраняет порядок identity -> status/kind ->
notes/counts -> compact actions. Вся row может иметь один понятный detail link,
но nested buttons не должны создавать invalid click targets.

## Reuse matrix

### Из Properties

| Pattern/component | Reuse | Category-specific boundary |
| --- | --- | --- |
| directory shell, URL search/view normalization | да | три views и grouping по kind |
| `use*Collection`, authoritative replacement | pattern | новый DTO/capabilities, не импортировать Property hooks |
| `WorkbenchPanel` create, dirty close | да | kind explanations and duplicate-name errors |
| `ExpansionPanel` edit | да | detail route, kind-impact confirmation |
| `ConfirmationDialog`, Toast, retry notices | да | rule/delete blockers принадлежат Categories |
| responsive records and quiet row actions | да | columns identity/kind/usage/notes |
| optimistic `updatedAt` recovery | да | category-specific error codes |

### Из Accounts и Reports

| Pattern/component | Reuse | Граница |
| --- | --- | --- |
| detail route loader/request-state shell | да | Category API/read model local |
| account ledger pagination/query precedent | да | category operation DTO не импортирует Account feature |
| Reports query preservation and `MoneyValue` | да | all calculations stay server-side |
| `ReadOnlyFinancialRow` financial history | да | category detail supplies its own prepared facts |
| report filter route construction | да | canonical link becomes `/app/categories/:id` |
| correction forms/business mapping | нет | Categories does not edit Operations |

### Из UI Foundation

Переиспользовать `Button`/`RouterButtonLink`, `ActionStack`, `StatusLabel`,
`Tag`, `Field`, `Fieldset`, `FormGrid`, `FormActions`, `FormErrorSummary`,
`WorkbenchPanel`, `ExpansionPanel`, `ConfirmationDialog`, `InlineNotice`,
`RequestState`, `WorkbenchEmptyState`, `WorkbenchPagination`,
`ResponsiveRecordCollection`, `ReadOnlyFinancialRow`, `MoneyValue`,
`ToastViewport`, `Icon`,
`PageFrame`, `PageHeader`, `WorkbenchSurface/Header/Toolbar/Content`.

`SearchableSelect` нужен в consumers, но category form использует небольшой
fixed kind choice и не требует searchable select. Повторный detail-аудит
выделил один новый устойчивый shared contract — `ReadOnlyFinancialRow` для
финансовых фактов без действий, focus и expansion. Feature CSS остаётся в
`frontend/app/features/categories/*.module.css`; Accounts/Reports/Properties
CSS и legacy `app.css` не импортируются.

## Accessibility и responsive acceptance

- один page-level primary CTA; row open/edit/archive не конкурируют с ним;
- visible labels и concise helper text для каждого kind;
- `aria-invalid`, described errors, error summary и focus first invalid;
- panel/dialog focus trap, trigger focus return и dirty-close confirmation;
- buttons/links имеют различимые accessible names и target около 44 px;
- status/kind/read-only не кодируются только цветом;
- pending controls disabled, mutations защищены от double submit;
- delete confirmation называет category и blockers/irreversibility;
- 1440: compact scan без repeated full-size buttons;
- 920: no shell/content overflow, stable operation columns/list switch;
- 390: no horizontal overflow, first meaningful records не скрыты chrome;
- Mocha и Latte имеют одинаковую geometry и semantic contrast;
- reduced motion respected для toast/highlight/panel transitions.
