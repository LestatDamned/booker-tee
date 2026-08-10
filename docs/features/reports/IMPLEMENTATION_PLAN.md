# Reports monthly XLSX export: план реализации

Статус: шаги 1–4 implemented 2026-08-10; ручной authenticated
browser smoke pending.

Шаги выполняются по порядку. Каждый шаг оставляет проверяемый срез и не
добавляет infrastructure будущих форматов или background jobs.

## Целевая граница

```text
React Reports download link
  -> GET /api/v1/reports/export.xlsx?month=YYYY-MM&currency=CCC
  -> MonthlyReportReader
       -> ReportingOverviewReader
       -> ReportsRepository.list_operation_entries(..., limit=10_001)
  -> build_monthly_report_xlsx(...) in thread pool
  -> binary XLSX response
```

Планируемая структура:

```text
src/app/features/reports/
  application/
    monthly_export.py
  monthly_report_xlsx.py
  repository.py

src/app/api/v1/reports/
  dependencies.py
  parameters.py
  router.py

frontend/app/features/reports/
  reports-page.tsx
```

`MonthlyReportReader` строит application data. `monthly_report_xlsx.py` только
сериализует эти данные в XLSX. Router владеет HTTP headers и API errors.
Новый generic export layer, Protocol для одного writer или таблица jobs не
нужны.

## Шаг 1. Month contract и operation projection

Статус шага: completed 2026-08-10.

### Результат

Application валидирует месяц и валюту, переиспользует текущие Reports итоги
и получает bounded список confirmed `MoneyEntry` без дублирования из-за
import provenance.

### Реализовать

- разбор `month=YYYY-MM` и вывод первого/последнего дня через Python stdlib;
- `ReportOperationEntryRow` с датами, type, source, account, signed amount,
  currency, category, property, description, provenance, operation id и entry order;
- `ReportsRepository.list_operation_entries(...)` с видимыми workspace, status,
  month и currency predicates;
- deterministic provenance aggregate, который не умножает `MoneyEntry`;
- `LIMIT 10_001` и `MonthlyExportTooLargeError` при превышении `10_000`;
- `MonthlyReportData` и `MonthlyReportReader`, переиспользующий
  `ReportingOverviewReader` для authoritative aggregates.

Не использовать Reports `_apply_profit_filters()` для operation projection: он
намеренно исключает transfer. Export projection фильтрует confirmed entries,
но включает оба движения transfer.

### Тесты

- leap-year February и December/January boundaries;
- invalid month отклоняется до database reads;
- unavailable currency отклоняется;
- query имеет workspace, confirmed, inclusive month и currency predicates;
- income/expense имеют одну entry row, transfer — две;
- manual/import/debt/system source сохраняется;
- несколько linked raw rows не умножают entry rows;
- `10_000` rows разрешены, `10_001` возвращают bounded error;
- foreign workspace entries не видны.

### Exit gate

Focused application/repository tests доказывают полную финансовую выборку
одного месяца без FastAPI и `openpyxl`.

## Шаг 2. XLSX builder

Статус шага: completed 2026-08-10.

### Результат

Чистый sync builder превращает `MonthlyReportData` в валидный XLSX без
обращения к database, FastAPI и storage.

### Реализовать

- `build_monthly_report_xlsx(report) -> bytes`;
- пять стабильных листов из specification;
- один набор переиспользуемых header/money/date styles без design system
  для одного workbook;
- numeric money cells, date cells, freeze panes, column widths и autofilters;
- explicit text cells для untrusted descriptions, names и filenames;
- stable empty sheets с headings;
- `BytesIO` output без temp или persisted files.

Не добавлять formulas, macros, charts, pivot tables, images или XLSX template.

### Тесты

Тесты строят workbook в памяти и повторно открывают его через
`openpyxl.load_workbook`. Binary golden files не коммитятся.

- names и order пяти листов;
- authoritative summary/account/category/property values;
- transfer с общим operation id и двумя entry rows;
- numeric money/date cell types и number formats;
- imported filename и source row;
- пустой месяц;
- strings с `=`, `+`, `-` и `@` остаются text, а не formulas.

### Exit gate

Builder tests проходят без database и HTTP; Excel-compatible parser открывает
книгу без repair warning.

## Шаг 3. API download

Статус шага: completed 2026-08-10.

### Результат

Authenticated endpoint синхронно отдаёт bounded monthly XLSX, а XLSX-сборка
не блокирует async event loop.

### Реализовать

- dependency composition из current `AsyncSession`, `ReportsRepository`,
  `ReportingOverviewReader` и `MonthlyReportReader`;
- `GET /api/v1/reports/export.xlsx`;
- API mapping для invalid month, invalid currency и over-limit error;
- XLSX build через thread pool;
- exact media type, safe filename, `Content-Disposition` и
  `Cache-Control: private, no-store`;
- safe timing/size metrics, если в проекте есть подходящий текущий
  instrumentation path. Не вводить metrics framework ради одного endpoint.

### Тесты

- unauthenticated request;
- viewer/read-only workspace member может скачать видимый отчёт;
- invalid month/currency и over-limit error envelopes;
- response headers и filename;
- response body открывается `load_workbook`;
- foreign workspace fixtures не попадают в workbook;
- export не создаёт database rows и не пишет document storage.

### Exit gate

Focused API tests доказывают auth, workspace isolation, headers, bounded failure
и валидный XLSX response.

## Шаг 4. React entry point и release checks

Статус шага: completed 2026-08-10.

### Результат

Reports показывает понятное same-origin download action только для full
calendar month.

### Реализовать

- переиспользовать current Reports period helpers для проверки full month;
- добавить `Скачать отчёт` как native same-origin link для полного месяца и
  disabled-кнопку с видимым пояснением для остальных периодов;
- не загружать operation rows в React и не собирать client-side Blob;
- показать краткое пояснение для немесячного периода;
- не менять Reports financial presentation и не добавлять export modal.

### Тесты

- full calendar month строит URL только с `month` и `currency`;
- all-time и arbitrary range не дают export action;
- month navigation обновляет export URL;
- action доступен с клавиатуры и имеет понятное accessible name;
- existing Reports route tests не меняют financial behavior.

### Release checks

```bash
uv run ruff format .
uv run ruff check .
uv run ty check .
uv run pytest tests/features/reports tests/api/test_reports_api.py -q

cd frontend
npm run format:check
npm run lint
npm run typecheck
npm run test -- reports
npm run build
```

До релиза вручную скачать минимум три файла:

1. пустой месяц;
2. обычный месяц с manual/import/transfer;
3. fixture с длинными текстами, inactive references и formula-like
   description.

### Exit gate

Канонический Reports screen скачивает корректный месячный XLSX; backend,
frontend и manual smoke gates пройдены.

## После релиза

После первой рабочей версии собираются только bounded technical metrics. Scope
не расширяется автоматически. Новое product decision нужно, если понадобятся:

- произвольные периоды;
- несколько валют;
- больше `10_000` movements;
- background generation и file retention;
- другие форматы или scheduled delivery.
