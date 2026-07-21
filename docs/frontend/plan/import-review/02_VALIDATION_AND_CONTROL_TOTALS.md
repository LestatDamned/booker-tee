# Slice 02: Validation и Control Totals

Статус: planned.

## Результат

React review объясняет неопределенность parser/normalization, statement control
totals, ignored amounts и balance-chain mismatches, сохраняя traceability до
исходных данных.

## Vertical scope

- Добавить typed application validation DTO, полученные из domain validation
  reports, а не напрямую из `ReviewValidationPresenter` или stored JSON shape.
- Отдавать стабильные status/reason codes и decimal strings; пользовательский
  текст форматировать в React.
- Связать balance-chain problems со стабильными row IDs в application mapping,
  хотя persisted reports сейчас используют `row_index`.
- Отобразить document summary и row-level problems, не вычисляя confirmability в
  TypeScript.
- Протестировать unavailable totals, mismatch, needs-review,
  ignored-as-explained и balance-chain cases.

## Правило consistency

Любая последующая mutation, обновляющая validation, должна явно вернуть или
инвалидировать этот summary. Client не оставляет устаревшие control totals после
изменения status/posting строки.

## Exit gate

Validation truth остается в domain/application, raw data видимы, а React владеет
только presentation wording/formatting.
