# Reports: monthly XLSX export

Статус: implemented 2026-08-10; ручной authenticated browser smoke
pending.

## 1. Задача

Пользователь скачивает один XLSX-файл с полным проверяемым отчётом
за один календарный месяц. Файл объединяет итоги Reports и все
confirmed движения выбранной валюты.

Ограничение одним месяцем — часть product contract первой версии. Оно
сдерживает время ответа, память и размер файла, пока функция
проходит реальную эксплуатационную проверку.

## 2. Входной контракт

```http
GET /api/v1/reports/export.xlsx?month=2026-08&currency=RUB
```

Параметры:

- `month` — обязательный календарный месяц в формате `YYYY-MM`;
- `currency` — обязательный трёхбуквенный код валюты, доступной в
  current workspace.

Backend сам выводит первый и последний день месяца. Endpoint не
принимает `date_from`, `date_to` или unbounded period, поэтому месячную
границу нельзя обойти ручным HTTP request.

Успешный ответ:

```text
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="booker-tee_2026-08_RUB.xlsx"
Cache-Control: private, no-store
```

Авторизация и workspace isolation те же, что у `GET /api/v1/reports`. Любой
участник, которому доступен Reports read, может скачать тот же набор
данных. Отдельная export permission не вводится.

## 3. Состав отчёта

В файл входят только confirmed operations. `draft`, `needs_review`, `ignored` и
`duplicate` не смешиваются с official ledger. Если в workspace есть
документ на проверке, лист `Итоги` показывает нейтральное
предупреждение, но эти строки не попадают в финансовые таблицы.

Каждая книга имеет пять стабильных листов, даже если отдельный лист пуст:

### `Итоги`

- workspace;
- month и currency;
- момент формирования;
- income, expense и profit;
- opening balance, closing balance и balance change;
- текстовый статус результата: положительный, нулевой или
  отрицательный;
- отметка, что transfer не входит в income, expense и profit;
- отметка о наличии данных на проверке.

Итоги записываются authoritative backend values, а не Excel-формулами.
Первая версия не добавляет новые advice или AI-generated conclusions.

### `Счета`

- название счёта;
- active/inactive state;
- currency;
- opening balance;
- closing balance;
- balance change.

Лист повторяет Reports account balance policy: inactive account остаётся
видимым, если у него есть остаток или движение.

### `Категории`

- категория;
- active/inactive state;
- income;
- expense;
- profit.

`Без категории` сохраняется как явная строка.

### `Объекты`

- объект;
- active/inactive state;
- income;
- expense;
- profit.

Property не меняет financial semantics transfer.

### `Операции`

Одна строка соответствует одному `MoneyEntry`, а не всей `Operation`.
Поэтому income и expense обычно имеют одну строку, transfer — две,
а сложная adjustment может иметь больше.

Колонки:

1. Дата операции.
2. Дата проводки.
3. Тип операции.
4. Источник.
5. Счёт.
6. Движение по счёту.
7. Валюта.
8. Влияет на финансовый результат.
9. Категория.
10. Объект.
11. Описание.
12. Документ импорта.
13. Строка импорта.
14. ID операции.
15. Номер движения.

Значения source показываются понятными пользователю метками:

```text
manual   -> Ручная
bank_pdf -> Импорт
debt     -> Долг
system   -> Системная
```

Импортная provenance не должна размножать `MoneyEntry`, если с одной
operation связано несколько raw rows. Projection возвращает одну строку
на `MoneyEntry` и детерминированно агрегирует имена документов и номера
исходных строк.

## 4. Финансовые правила

- money остаётся `Decimal` до границы XLSX;
- один файл содержит одну currency;
- income, expense и profit используют confirmed `affects_profit=true`;
- transfer виден в `Операции` и изменениях счетов, но исключён
  из profit aggregates;
- сумма account changes согласуется с общим balance change;
- месяц фильтруется по `Operation.operation_date`;
- archived счета, категории и объекты не исчезают из исторического
  отчёта.

## 5. XLSX contract

Используется уже установленный `openpyxl`. Новая dependency не нужна.

- деньги записываются numeric cells с форматом `#,##0.00`;
- даты записываются date cells, а не display strings;
- табличные заголовки закреплены, включён autofilter;
- внутри таблиц нет merged cells и hidden financial rows;
- все пользовательские строки принудительно записываются как text,
  чтобы `=`, `+`, `-` и `@` в начале описания не стали формулой;
- workbook не содержит macros, external links или data connections;
- файл формируется в памяти и не сохраняется в document storage.

## 6. Performance boundary

Первая версия синхронно отдаёт download в рамках одного HTTP request.
Database reads остаются async; синхронная XLSX-сборка выполняется в
thread pool и не блокирует event loop.

Жёсткий лимит — `10_000` exported `MoneyEntry`. Query запрашивает
`10_001` строку; превышение возвращает API error до начала XLSX-сборки:

```json
{
  "code": "monthly_export_too_large",
  "message": "В выбранном месяце больше 10 000 движений."
}
```

Минимальные safe metrics без private labels и amounts:

```text
report_export_rows
report_export_query_seconds
report_export_build_seconds
report_export_bytes
```

Background job, хранение файла и status polling появляются только после
измеренной проблемы: регулярного времени более `10–15` секунд, больших
файлов или конкурирующих экспортов, которые мешают API workload.

## 7. UI contract

Кнопка `Скачать отчёт` доступна, когда Reports открыт на полном календарном
месяце. Для `Всё время` и произвольного диапазона UI не строит export URL,
показывает кнопку disabled с tooltip `Выберите полный месяц, чтобы скачать
отчёт`. Нативный tooltip доступен по hover, а то же пояснение — screen reader
при keyboard focus.

Кнопка — обычная same-origin download link. Frontend не получает financial
rows для client-side generation и не дублирует XLSX formatting.

## 8. Errors

- `400 invalid_report_month` — `month` не соответствует `YYYY-MM`;
- `400 invalid_report_currency` — валюта недоступна current workspace;
- `401/403` — общий API auth contract;
- `422 monthly_export_too_large` — превышен лимит движений;
- `500` — sanitized export failure без ячеек, описаний и raw payloads в
  logs или response.

## 9. Out of scope

- период больше или меньше календарного месяца;
- несколько валют в одной книге;
- неподтверждённые raw rows в financial tables;
- CSV, PDF и другие export formats;
- charts, pivot tables и interactive workbook logic;
- background queue, export jobs, object storage и email delivery;
- scheduled exports;
- AI-generated advice и period comparison;
- общий exporter Protocol, plugin system или report builder.

## 10. Acceptance criteria

1. Файл открывается Excel-compatible application без repair warning.
2. В файле только данные authenticated current workspace, month и currency.
3. Income, expense, profit и account balances равны Reports API для того же
   месяца.
4. Transfer имеет две entry rows и не влияет на profit.
5. Manual и imported operations имеют явный source; imported row сохраняет
   document provenance.
6. Empty month возвращает валидную книгу с пятью листами.
7. Foreign workspace references и недоступная currency не раскрывают данные.
8. Описание, начинающееся с `=`, остаётся text и не становится formula.
9. При `10_001` movements XLSX не строится, API возвращает bounded error.
10. Файл не записывается в uploaded document storage и не попадает в logs.
