# Reports

Статус: месячный XLSX-экспорт реализован 2026-08-10;
ручной authenticated browser smoke pending.

Reports строит проверяемую финансовую картину периода из confirmed
`Operation + MoneyEntry`. Первая версия XLSX-экспорта намеренно
ограничена одним календарным месяцем и одной валютой. Это
рабочий тестовый scope, а не общая платформа экспортов.

Экспорт должен:

- повторять authoritative итоги текущего Reports read model;
- показывать счета, категории, объекты и все confirmed движения
  выбранного месяца;
- различать ручные, импортированные, debt и system operations;
- показывать обе стороны transfer, но не считать его income, expense
  или profit;
- отдавать файл синхронным authenticated HTTP response без
  хранения на сервере.

Первая версия не включает background jobs, историю экспортов,
произвольные периоды, смешивание валют, AI-выводы, графики или
пользовательские XLSX-шаблоны.

## Документы

- [`MONTHLY_XLSX_EXPORT.md`](MONTHLY_XLSX_EXPORT.md) — product, data, API,
  workbook, security и performance contract;
- [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) — последовательные шаги,
  проверки и exit gates.

Общие финансовые инварианты остаются в
[`docs/domain/DOMAIN_MODEL.md`](../../domain/DOMAIN_MODEL.md), а действующая
browser/API архитектура — в
[`docs/architecture/ARCHITECTURE.md`](../../architecture/ARCHITECTURE.md).
