# Reports

Статус: действующий Reports и monthly XLSX contract.

Reports читает только confirmed `Operation + MoneyEntry` и группирует результат
по currency. Transfer показывается как движение между accounts, но не входит в
income, expense, profit или property ROI.

## Period reports

Overview, category/property breakdowns и operation lists используют один
backend-owned reporting read model. URL хранит period и filters; React не
пересчитывает финансовые итоги из загруженных строк.

Mixed currencies не складываются в одно число. Missing category/property
показывается как отдельная явная группа.

## Monthly XLSX

Первая версия принимает один calendar month и одну currency и отдаёт
authenticated synchronous HTTP download без серверного хранения файла.

Workbook содержит:

- `Итоги` — income, expense, profit и transfer turnover;
- `Счета` — opening, inflow, outflow и closing;
- `Категории` — confirmed income/expense totals;
- `Объекты` — confirmed property-linked result;
- `Операции` — полный проверяемый список движений периода.

Operations sheet показывает operation id, date, type, source, description,
account/transfer side, amount, currency, category, property and status. Обе
стороны transfer видимы, но financial totals не считают их income/expense.

Файл использует стабильные sheet/column names, ISO dates и numeric money cells;
formula injection из пользовательского текста блокируется. Workspace scope,
role и выбранная currency проверяются сервером. Empty month возвращает
валидный workbook с нулевыми итогами.

Не входят без отдельной потребности: background jobs, export history, arbitrary
periods, mixed-currency totals, charts, AI commentary и custom templates.
