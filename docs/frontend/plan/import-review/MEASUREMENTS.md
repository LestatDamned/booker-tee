# Stage 06: измерения Import Review

Измерено: 2026-07-22.

Цель — проверить replacement gate, а не определить production SLA. Browser
измерения выполнены на realistic XLSX из трёх строк; payload baseline отдельно
зафиксирован на детерминированном typed fixture из одной строки.

## Response и production assets

| Часть | Raw | Gzip | Комментарий |
| --- | ---: | ---: | --- |
| `ImportReviewApiResponse`, 1 row fixture | 2,376 bytes | 995 bytes | JSON без HTML, action URLs, labels и layout |
| import-review route JS | 36,520 bytes | 10,570 bytes | cacheable production chunk |
| import-review route CSS | 10,110 bytes | 2,090 bytes | feature-local CSS Module |

Legacy route возвращал целую Jinja-страницу при GET и HTML/OOB fragments после
mutation. Точный byte-for-byte realistic legacy snapshot до начала Stage 06 не
был заморожен, поэтому ложное численное сравнение не записывается. После
replacement удалено более 8 тысяч строк legacy adapter/templates/tests и около
2 тысяч строк его CSS; повторяемый financial payload теперь является typed JSON,
а JS/CSS кэшируются отдельно.

## Query shape

Первый вариант transfer read model выполнял два candidate query на каждую
непроведённую строку. Перед Go это было исправлено точечно:

- raw-row transfer candidates читаются одним workspace-scoped batch query;
- manual transfer candidates читаются одним workspace-scoped batch query;
- relationship loads остаются `selectinload` и не зависят от количества rows;
- application test фиксирует один repository call для списка строк, включая
  linked row, вместо цикла запросов.

Таким образом query shape остаётся row-independent. Exact SQL round-trip count
зависит от количества `selectinload` relationship groups, но не растёт на два
запроса с каждой строкой, как до gate.

## Interaction и browser gate

Playwright `review_interactions` прошёл 51 страницу: desktop 1440 px, tablet
920 px и mobile 390 px. Для каждого viewport проверены canonical React route и
historical redirect. React сценарий реально выполняет:

1. apply-rules и authoritative reconciliation;
2. danger confirmation/cancel с focus;
3. server draft evaluation;
4. confirm/post строки зарплаты;
5. появление undo capability после commit;
6. transfer matching panel;
7. отсутствие horizontal overflow, console/page/request errors.

Отдельный искусственный latency budget не вводился. Gate проверяет завершение
каждой network interaction в существующем browser timeout 8 секунд; все шаги
прошли. Если появятся production traces, SLA оформляется отдельно, а не
угадывается по локальному запуску.

## Вывод

Go: feature-local state и полные committed snapshots достаточны. Cache/state
library не нужна; обнаруженная performance проблема была в server query shape и
исправлена на владельце данных, а не клиентским cache.

## Stage 09E: большая очередь

Дополнительно измерено 2026-07-23 на синтетическом browser payload из 250
неразобранных строк. Это локальный engineering baseline, а не production SLA.
Один и тот же typed response раскрывался на desktop `1440×1000`, tablet
`920×900` и mobile `390×844`.

До ограничения initial DOM полный список создавал около `46 900` DOM nodes.
Локально он становился готов за `418–523 ms`, но такой DOM избыточен как
начальное состояние даже при приемлемом времени render.

После введения feature-local `Показать ещё`:

| Метрика | Desktop | Tablet | Mobile |
| --- | ---: | ---: | ---: |
| Payload | 403,519 bytes | 402,766 bytes | 402,766 bytes |
| Initial visible rows | 50 | 50 | 50 |
| Initial ready | 292.1 ms | 287.0 ms | 256.4 ms |
| Initial DOM nodes | 9,507 | 9,507 | 9,507 |
| Явное раскрытие до 250 rows | 1,637.2 ms | 1,496.4 ms | 1,542.6 ms |
| Expanded DOM nodes | 46,903 | 46,903 | 46,903 |
| Scroll settle | 15.7 ms | 26.2 ms | 8.0 ms |
| Long tasks | 0 | 0 | 0 |

Решение: server pagination и virtualization dependency пока не вводятся.
Очередь сохраняет server ordering и полный financial payload, но сначала
рендерит 50 строк. Пользователь раскрывает следующие блоки по 50 строк, а
visible count хранится в `rows` query parameter вместе с рабочим `filter`.
Browser Back/Forward восстанавливает оба navigation context без отдельного
global store.
