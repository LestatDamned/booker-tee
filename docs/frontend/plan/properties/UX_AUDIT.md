# Properties SSR UX/UI audit

Статус: observed baseline и target guidance, не implementation spec.

## Метод

Проверены template/CSS/JS, SSR presenter tests и локальный authenticated
Playwright scenario `realistic`:

```bash
UV_CACHE_DIR=/tmp/booker-tee-uv-cache uv run python scripts/ui_audit.py \
  --base-url http://127.0.0.1:8000 \
  --authenticated --scenario realistic --path properties \
  --output-dir /tmp/booker-tee-properties-ssr-audit
```

Результат: 3/3 pages passed на 1440x1000, 920x900 и 390x844; HTTP 200,
horizontal overflow 0, console/page/request/UX assertion errors отсутствуют.
Screenshots являются временными audit artifacts в `/tmp` и не добавляются в
активную документацию.

## Что работает

- Название страницы и краткое объяснение быстро дают базовый смысл Property.
- Name является главным row identity; UUID и технические детали не показаны.
- Status передан текстом, не только цветом.
- Address и long names переносятся; на контрольных ширинах нет page overflow.
- Desktop row компактна, tablet/mobile actions перестраиваются в доступную
  двухкнопочную сетку.
- Labels видимы, required name использует native required.
- Server validation сохраняет create/edit draft и открывает нужную form area.
- Empty state различает writer и read-only participant.
- Recent-created feedback и row anchor сохраняют контекст после full reload.

## Основные проблемы

### Information hierarchy

- Tutorial hint и example strip занимают место до реестра, но список не
  показывает count, search или status grouping.
- Active и archived rows смешаны в одном потоке; порядок определяется enum,
  не явным пользовательским выбором.
- Short name и address показаны как неименованные metadata; различие может быть
  неочевидно без формы.
- Page-level Reports link не сохраняет конкретный property context.
- Row не сообщает последствие archive: объект исчезнет из active pickers, но
  история и существующие rules останутся.

### Interaction и feedback

- Create `<details>` одновременно показывает текст «Открыть Закрыть» в
  проверенном rendered state.
- Edit button программно кликает visually-hidden `<summary>`, но не выставляет
  `aria-expanded` и не управляет focus при open/close.
- Field error имеет `role=alert`, но не связан с control через
  `aria-invalid`/`aria-describedby`; focus не переводится к invalid field.
- Archive выполняется сразу, без impact copy, pending state или защиты от
  double submit.
- Full-page POST/redirect даёт feedback через URL/banner; локальная ошибка
  lifecycle перестраивает всю страницу.
- Primary styling у «Изменить объект» визуально громче самого content outcome.

### Responsive и shell

- 920 px: legacy global navigation переносится на две строки и увеличивает
  расстояние до рабочей области.
- 390 px: brand/menu, workspace/upload и page panel создают несколько уровней
  chrome; основная row начинается заметно ниже fold.
- Mobile сохраняет workflow и не overflow-ит, но action/report controls занимают
  полную ширину до primary content.
- SSR существует только в legacy visual/theme system; нет parity с React
  AppShell, Mocha/Latte/test theme и shared focus contract.

## Целевая информационная иерархия

```text
AppShell
└─ PageFrame
   └─ WorkbenchSurface
      ├─ WorkbenchHeader
      │  └─ PageHeader: workspace/count, Объекты, короткое описание, Отчёты
      ├─ WorkbenchToolbar
      │  ├─ WorkbenchSearch
      │  ├─ SelectionTabs: lifecycle views после решения D1
      │  └─ Новый объект
      ├─ read-only / recoverable InlineNotice
      ├─ WorkbenchContent
      │  ├─ WorkbenchEmptyState
      │  └─ ResponsiveRecordCollection
      │     └─ property identity + short name + address + StatusLabel + actions
      ├─ WorkbenchPanel: create
      ├─ ExpansionPanel: one edited row
      ├─ ConfirmationDialog: archive impact, если принято D2
      └─ ToastViewport
```

Description должен объяснять аналитическую роль объекта одной строкой. Примеры
можно оставить в empty/create context, а не как постоянную полосу над каждой
непустой коллекцией.

## Reuse matrix

### Из Accounts

| Pattern/component | Reuse | Граница |
| --- | --- | --- |
| `PageFrame -> WorkbenchSurface -> WorkbenchHeader/PageHeader` | да | Properties владеет copy и row content |
| `WorkbenchSearch` + URL normalization | да | искать name, short name, address; без generic search abstraction |
| `SelectionTabs` и counts | да после D1 | status vocabulary остаётся server/domain-owned |
| `ResponsiveRecordCollection` | да | feature задаёт desktop columns и mobile order |
| `WorkbenchPanel` create flow | да | новый Property form, не Account form |
| `ConfirmationDialog`, retry `InlineNotice`, Toast | да | lifecycle impact отличается от Account |
| authoritative local collection update | да | no optimistic mutation; response заменяет row |

Account feature CSS, account DTO и lifecycle functions не импортируются.

### Из Reports

| Pattern/component | Reuse | Граница |
| --- | --- | --- |
| stable `property_id` URL filter | да | Properties только строит route; Reports считает данные |
| query-preserving navigation semantics | да | не копировать report filter implementation в feature |
| responsive record/table precedent | как reference | Property rows не содержат money matrix |
| `MoneyValue` и report aggregation UI | нет | directory не вычисляет ROI |

### Из UI Foundation

Переиспользовать `Button`/`RouterButtonLink`, `ActionStack`, `StatusLabel`,
`Tag` при реальной secondary classification, `Field`, `FormGrid`,
`FormActions`, `FormError`, `FormErrorSummary`, `WorkbenchPanel`,
`ExpansionPanel`, `ConfirmationDialog`, `InlineNotice`, `RequestState`,
`WorkbenchEmptyState`, `ToastViewport` и общий `Icon`.

Новый shared component не требуется по текущему аудиту. Property-specific
layout остаётся в `features/properties/*.module.css`; нельзя импортировать
Accounts/Reports CSS или legacy `app.css`.

## Accessibility и responsive acceptance

- semantic h1/list/table structure и один page-level primary CTA;
- visible labels, `aria-invalid`/described errors, summary links и focus на
  first invalid control;
- create panel и edit expansion возвращают focus trigger; dirty close требует
  confirmation;
- edit control сообщает `aria-controls` и `aria-expanded`;
- status/archived/read-only не кодируются только цветом;
- standalone actions имеют hit area около 44 px, pending/disabled states;
- 1440: compact desktop collection, actions не конкурируют с identity;
- 920: React sidebar/mobile shell contract без page-level overflow;
- 390: content order identity -> status/metadata -> actions -> expansion, без
  fixed controls поверх errors;
- Mocha и Latte сохраняют одинаковую geometry; test theme выявляет raw palette;
- reduced motion отключает recent-row highlight animation.

