# Reports Migration Nuances

Статус: обязательный checklist для всех Reports slices.

Этот документ фиксирует места, где визуально успешный перенос может оставить
финансовую ошибку, скрытый performance regression или второй presentation
contract.

## 1. Валюта — часть финансового ключа

Текущая сумма операций без currency filter, подписанная default currency
workspace, недопустима.

Правила:

1. Reporting aggregation опирается на explicit `MoneyEntry.currency`.
2. Income, expense, profit, category и property totals строятся только для
   одной applied currency.
3. Default applied currency — `workspace.default_currency`.
4. Выбранная currency всегда видима рядом с KPI и breakdowns.
5. Смена account не должна молча конвертировать или переименовывать сумму.
6. Если account/currency filters не дают данных, UI показывает честный filtered
   empty state.
7. Exchange-rate conversion не входит в migration scope.
8. Decimal values остаются strings на JSON boundary и `Decimal`/`Numeric` на
   backend; `float` не используется.

Dashboard и Chat month/category summaries обязаны передавать выбранную currency
в reader, а не только подписывать результат default currency после вычисления.

## 2. Transfers и знак суммы

- Только confirmed operations участвуют в официальном отчёте.
- `affects_profit=false` исключает internal transfers из KPI и breakdowns.
- Account balances по-прежнему видят обе стороны transfer.
- Category/property filter не должен случайно вернуть transfer в profit totals.
- Pure summary tests сохраняются как characterization, но SQL aggregate tests
  становятся главным доказательством production path.

## 3. Identity важнее display name

Category и Property grouping выполняется по UUID, не по имени.

DTO row содержит минимум:

```text
categoryId/propertyId
name
currency
income
expense
profit
```

Две сущности с одинаковым именем остаются двумя строками. Uncategorized не
маскируется произвольным UUID: это явная nullable/system group с понятной
семантикой.

## 4. Семантика периода balances

Profit sections используют `date_from..date_to`. Balance является snapshot:

```text
initial balance + confirmed entries through date_to
```

Он не должен зависеть от category/property/date_from. UI обязан подписать
секцию как «Балансы на DD.MM.YYYY» или «Балансы на сегодня/за всё время» по
нормализованному server fact `asOf`. Нельзя визуально создавать впечатление,
что balance относится только к выбранной категории или диапазону.

## 5. Filter validation и historical references

- Server отклоняет `date_from > date_to` стабильным `400/422` contract.
- UUID/date/currency/page size валидируются на HTTP boundary.
- Любая выбранная entity проверяется как принадлежащая текущему workspace.
- Filter options включают inactive/archived entity, если она нужна для
  исторических данных или текущего selected value.
- Archived state передаётся как факт и отображается текстом, не только цветом.
- Unknown/deleted foreign filter не должен раскрывать данные другого workspace.

## 6. Read path без side effects

`GET /api/v1/reports` не вызывает seeding, `flush`, `commit` или lifecycle
repair. Category defaults создаются отдельным уже существующим write workflow,
а report read использует доступные reference rows как есть.

Replacement tests должны падать при неожиданном write/commit. Это отдельный
gate, а не только code-review замечание.

## 7. Bounded и постоянное число запросов

Запрещён production shape:

```text
list accounts -> balance query for every account
list all operations -> aggregate in Python
list all documents -> choose first review item
```

Целевой read состоит из ограниченного числа workspace-scoped queries:

1. filter/reference options;
2. account balance aggregate;
3. KPI aggregate;
4. category aggregate;
5. property aggregate;
6. bounded uncategorized page + count;
7. optional single next-review document.

Количество SQL queries не растёт линейно с account/operation/document count.
Uncategorized имеет server-enforced maximum page size и deterministic order с
UUID tie-breaker.

## 8. Общие consumers и границы DTO

React response DTO не становится общим объектом всего приложения.

- Dashboard получает только нужный reporting snapshot.
- Chat readers получают currency-safe summary/category/balance projections.
- Categories использует узкую pure summary policy/value object либо собственный
  aggregate query, но не React DTO.
- Jinja presenter labels/URLs/sort models не переходят в application layer.

Рекомендуемая структура после refactor:

```text
features/reports/
  application/overview.py
  domain/summary.py
  repository.py
api/reports.py
```

Имена и разбиение уточняются по фактической cohesion. Не создавать фасады и
интерфейсы, у которых нет второго consumer или тестовой пользы.

## 9. URL и navigation state

URL хранит applied filters, category sort и uncategorized page. Локальный draft
формы не меняет результаты до `Применить`.

- Apply нормализует URL и сбрасывает uncategorized page на первую.
- Reset удаляет financial filters и pagination, возвращая default currency.
- Back/Forward и reload восстанавливают тот же applied state.
- Month navigation сохраняет entity/currency/sort filters и сбрасывает только
  несовместимую pagination.
- Canonical deep link работает без предварительной навигации через SPA.

## 10. UI composition и accessibility

Первый перенос сохраняет существующий semantic token/component system; новые
fonts, raw colors, glass effects и charts не добавляются.

Переиспользовать:

- `MoneyValue` для amount + currency + tabular numerals;
- `ResponsiveRecordCollection` для desktop table/mobile records;
- `AppliedFilterSummary` для читаемого applied state;
- существующие Page/Workbench/filter/empty/error primitives.

Обязательные UX gates:

- currency видима, а смысл не передаётся только цветом;
- sortable headers — настоящие buttons/links с `aria-sort`;
- icon-only period actions имеют accessible names;
- focus после route change и ошибок предсказуем;
- touch targets не меньше 44×44 px;
- нет horizontal page scroll на 390 px;
- loading/error/empty/filtered-empty states различимы;
- reduced motion поддерживается; декоративная анимация не нужна.

Category/property tables на mobile превращаются в короткие records, а не в
сжатую широкую таблицу. Графики откладываются до отдельной доказанной
аналитической потребности и всегда требуют табличной альтернативы.

## 11. Cutover не равен redirect

Reports считается перенесённым только после смены всех canonical consumers и
удаления HTML presentation. Redirect остаётся узкой исторической
совместимостью и не оправдывает сохранение Jinja router/presenter/templates.

До удаления каждого CSS selector выполнить consumer search. Общая
`.report-table` остаётся до Categories cutover, потому что у неё есть named SSR
consumer.
