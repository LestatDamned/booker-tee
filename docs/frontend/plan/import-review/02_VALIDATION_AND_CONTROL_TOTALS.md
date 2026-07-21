# Slice 02: Validation и Control Totals

Статус: completed.

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

## Реализовано

- Выделен общий application calculation boundary, который строит свежий domain
  `StatementValidationReport` из строк документа и control totals последней
  parse attempt. Read endpoint не зависит от persisted `validation_report_json`
  и legacy `ReviewValidationPresenter`.
- Typed read model и API отдают стабильные validation/reason/problem codes,
  counts и decimal strings. Отдельно различаются необъясненный mismatch и
  mismatch, полностью объясненный ignored-строками.
- Balance-chain mismatch преобразуется из position index domain report в
  стабильные current/previous item UUID и реальные `row_index` до API boundary.
- React показывает validation summary, control totals, ignored/unexplained
  суммы и row-level problem рядом с соответствующим UUID-якорем. TypeScript не
  вычисляет status, confirmability или финансовую разницу.
- Покрыты unavailable, needs-review, control-total mismatch,
  ignored-as-explained и balance-chain cases; production build и responsive
  Playwright audit на 1440/920/390 прошли.

Consistency-правило остается обязательным для будущих mutation slices: после
изменения строки response должен вернуть или инвалидировать validation summary.
