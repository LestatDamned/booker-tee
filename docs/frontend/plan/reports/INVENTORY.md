# Inventory: Reports

Статус: verified planning inventory.

Проверено: 2026-07-31.

## Scope

Текущий authenticated entry point:

```text
GET /reports
```

Query parameters:

```text
date_from
date_to
account_id
category_id
property_id
category_sort
category_sort_dir
```

В scope переноса входят overview, period navigation, exact filters, KPI,
account balances, category/property breakdowns, uncategorized operations,
empty states и category sorting.

Не входят новые forecasting, budgets, ROI, exchange-rate conversion, exports,
charts, saved reports или произвольный report builder.

## Наблюдаемое SSR-поведение

### Период и фильтры

- Есть предыдущий/следующий месяц, текущий месяц и всё время.
- Exact filters поддерживают диапазон дат, счёт, категорию и объект.
- Month navigation сохраняет entity filters и category sort.
- Некорректный UUID/date возвращает `400`.
- `date_from > date_to` сейчас не отклоняется.
- Options accounts/properties берутся только из active lists; историческая
  выбранная archived entity может исчезнуть из selector.

### Summary и balances

- KPI показывает доходы, расходы и прибыль.
- Transfers исключаются через `affects_profit`.
- KPI подписан `workspace.default_currency`, хотя операции не фильтруются и не
  группируются по currency.
- Balances считаются по каждому active account отдельно.
- Balance учитывает `date_to` и optional `account_id`, но не `date_from`,
  category или property; UI не объясняет эту асимметрию явно.

### Breakdowns

- Category rows содержат доходы, расходы и прибыль; uncategorized получает
  отдельную группу.
- Сортировка category table выполняется через HTMX partial; default `name asc`,
  числовые колонки по умолчанию `desc`.
- Category identity уже сохраняет UUID.
- Property rows группируются по `property.name`, поэтому два объекта с
  одинаковым именем сливаются.
- Uncategorized section выводит все совпавшие операции без pagination/limit.

### Empty states

- Без account предлагается создать счёт.
- При document requiring review предлагается перейти к review.
- Иначе предлагается открыть Imports или загрузить выписку.
- Для next-review CTA загружаются все documents workspace, затем выбирается
  первый подходящий.

## Existing implementation

```text
src/app/features/reports/router.py
  -> ReportsService.build_overview(...)
  -> presentation/presenter.py
  -> templates/reports/index.html + _category_table.html
```

`ReportsService.build_overview()`:

- получает active accounts;
- делает отдельный balance query на каждый account;
- загружает все confirmed operations с relationships;
- агрегирует summary/categories/properties/uncategorized в Python.

SSR router дополнительно:

- повторно получает accounts;
- вызывает `CategoryService.list_or_seed_defaults()` во время GET;
- получает active properties;
- загружает все documents для одного empty-state CTA.

## Cross-feature consumers

Нельзя удалить `src/app/features/reports/service.py` вместе с SSR presentation:

- `src/app/features/dashboard/service.py` использует `ReportFilters`,
  `ReportsOverview`, `ReportsService`;
- `src/app/features/chat_integrations/use_cases/dashboard.py` использует
  `ReportsService` для month/category summaries и balances;
- `src/app/features/categories/service.py` использует
  `IncomeExpenseSummary` и `summarize_income_expense`.

При refactor каждый consumer переводится на узкий named contract. Dashboard и
Chat не должны зависеть от browser response schema; Categories не должен
зависеть от полного overview reader.

## Canonical link consumers

Проверить и обновить:

- `frontend/app/shell/app-shell.tsx`;
- legacy `templates/base.html`;
- dashboard summary;
- authenticated home quick actions;
- onboarding checklist;
- categories index;
- properties index;
- chat URL/menu builders, если они формируют reports link;
- workspace permission/return-path tests;
- `scripts/ui_audit.py`;
- generated OpenAPI schema.

## Legacy delete manifest

После общего replacement gate удалить:

- `src/app/features/reports/router.py`;
- `src/app/features/reports/presentation/`;
- `src/app/templates/reports/index.html`;
- `src/app/templates/reports/_category_table.html`;
- reports router inclusion из `src/app/main.py`;
- SSR presenter/template/HTMX-only tests;
- HTML `/reports` operation из generated OpenAPI types;
- Reports-specific legacy selectors после consumer search.

Сохранить/refactor:

- application/domain reporting contracts, нужные Dashboard/Chat;
- pure financial summary, если у него остаётся Categories consumer;
- workspace-scoped repository queries;
- server financial/application tests;
- historical GET redirect и focused redirect test.

`.report-table` нельзя удалять как общий selector, пока
`src/app/templates/categories/detail.html` остаётся runtime consumer. Reports
cutover удаляет только selectors, доказанно не используемые другими SSR pages.

## Existing tests baseline

Текущие focused tests находятся в:

- `tests/features/reports/test_reports.py`;
- `tests/features/reports/test_reports_template.py`.

Проверенный baseline вместе с ближайшими consumers:

```text
18 passed
```

Он покрывает pure summaries, transfer exclusion, URL/presenter behavior,
selected account/date and template empty states. Он не доказывает:

- multi-currency correctness;
- duplicate property identity;
- workspace isolation API contract;
- archived filter references;
- no-write GET;
- constant query count;
- bounded uncategorized results;
- API auth/runtime schema;
- invalid reversed date range.
