# React UI foundation

Статус: decision guide для существующих shared components.

Код в `frontend/app/ui`, tests и `/app/foundation` являются каталогом API и
states. Этот документ фиксирует только выбор и composition.

## Порядок выбора

1. Найти компонент с нужной ответственностью в `app/ui`.
2. Проверить его states и themes на `/app/foundation`.
3. Найти feature с похожим workflow.
4. Собрать страницу из shared components.
5. Оставить уникальные rules/layout внутри feature.
6. Выделять новый shared component только после повторения устойчивого контракта.

Внешнее сходство не доказывает общий contract.

## Базовая композиция

```text
PageFrame
  PageHeader
  InlineNotice / AppliedFilterSummary
  WorkbenchToolbar
  WorkbenchSurface
    RequestState | collection/selected record
  Toast or ConfirmationDialog
```

- `PageFrame/PageHeader` — shell страницы и primary action.
- `WorkbenchToolbar` — search, filters, tabs и secondary controls.
- `WorkbenchSurface/Panel/Row` — плотная financial collection.
- `ResponsiveRecordCollection` — table/card representation одного dataset.
- `RequestState` и `RouteStatePage` — loading, empty, error и retry.
- `MoneyValue`, `StatusLabel`, `Badge`, `Tag` — semantic values.
- `Field`, `PasswordInput`, `SearchableSelect` — accessible form controls.
- `ConfirmationDialog`, `Toast`, `InlineNotice` — consequence/feedback.
- `ExpansionPanel` — progressive detail, не скрытие primary task.

Не копируйте props в docs: открывайте defining TypeScript module.

## CSS ownership

```text
styles/tokens + themes  global semantic values
styles/foundation      reset, typography and app-level primitives
app/ui/<component>     shared component geometry/states
app/features/<feature> unique workflow/layout
```

Feature не переопределяет внутренние selectors shared component. Новый global
selector допустим только для действительно application-wide primitive.

## Forms

```text
native control
  -> Field/Fieldset
  -> feature draft
  -> API request mapper
```

Shared UI владеет label/hint/error geometry, error summary, focus and responsive
form layout. Feature владеет field names, conditional behavior, options,
business validation mapping, retry and success behavior. Используйте
`FormSection`, `FormGrid` и `FormActions` из существующей foundation,
если они уже подходят; не создавайте universal form schema.

## Checklist

- backend остаётся владельцем financial/permission policy;
- есть loading, empty, error, retry и stale/conflict behavior;
- primary action один, destructive отделён;
- applied filters отражены в URL;
- selected record имеет устойчивый deep link;
- keyboard/focus/dialog behavior проверен;
- 1440/920/390/320 px не ломают workflow;
- Mocha, Latte и test theme остаются читаемыми;
- новый shared component показан на `/app/foundation`.
