# Slice 04: Unknown Statement Mapping

Статус: active; шаги 4.1–4.3 завершены.

## Outcome

Пользователь выбирает исходную таблицу, настраивает колонки, получает
authoritative server preview, исправляет warnings/errors, при необходимости
сохраняет template и создаёт reviewable raw rows ровно один раз.

## Execution sequence

1. Зафиксировать workflow, hierarchy и responsive contract.
2. Добавить typed read/preview API и application contracts.
3. Собрать React draft, выбор таблицы, mapping form и preview.
4. Добавить idempotent import, optional template save и переход в Review.
5. Провести cutover, удалить legacy mapping и пройти browser gate.

## UX contract

Страница отвечает на три вопроса:

1. правильный ли источник выбран;
2. правильно ли поняты колонки;
3. можно ли безопасно создать строки для проверки.

Это один рабочий экран, а не линейная анкета и не dashboard. Он использует
общий `workbenchHeader`: счёт — основной identity, банк/валюта и имя файла —
вторичный контекст, состояние документа — справа. Повторный большой
`next step`/workflow banner здесь не нужен: текущая задача уже выражена
заголовком и единственной primary action.

Это desktop-first power tool. Основной целевой viewport — от 1024 px: mapping
требует одновременного сравнения исходных колонок, их ролей и результата.
Отдельный упрощённый mobile workflow пока не создаётся.

Desktop layout:

- экран использует доступную ширину как единый column-mapping workbench;
- глобальные параметры находятся в компактной строке над источником;
- роль каждой исходной колонки выбирается прямо в её заголовке;
- заголовок ролей и исходные строки находятся в одной таблице с общей сеткой
  колонок и одной локальной прокруткой;
- source table имеет bounded viewport, а не растягивает страницу всеми rows;
- authoritative preview расположен ниже источника; после запроса фокус
  результата переходит на него, а source остаётся непосредственно выше;
- нижняя action bar показывает актуальность preview и содержит
  `Обновить предпросмотр` / `Импортировать N строк`.

Настройка использует direct mapping и компактный global context:

- связь `исходная колонка → роль` видна без перевода взгляда между боковой
  панелью и таблицей;
- обязательные роли визуально отличимы, а необязательная роль может быть
  снята через `Не используется`;
- назначение уже занятой роли другой колонке меняет роли колонок местами и не
  создаёт временно некорректный duplicate mapping;
- способ суммы — взаимоисключающий выбор `Одна колонка` или
  `Списание + зачисление`;
- дата проводки, валюта из строки и остаток доступны среди ролей колонок, но не
  занимают отдельную панель;
- первая строка данных выбирается по видимому номеру строки, без раскрытия
  zero-based индекса;
- имя шаблона появляется как optional-настройка импорта после валидного
  preview, а не как часть результата.

Source picker показывает не голые номера, а страницу/таблицу, размеры и
короткие заголовки колонок. Analyzer suggestions предзаполняют форму; длинное
объяснение confidence/reasons скрыто под раскрываемым `Почему выбрано так`.

Preview использует тот же финансовый visual language, что Import Review:
дата, полное переносимое описание, сумма со знаком/semantic tone и текстовый
статус. Он отдельно показывает:

- сколько строк найдено всего;
- сколько корректно и сколько требует исправления;
- что preview ограничен выборкой;
- какие совместимые continuation tables войдут в import.

Ошибки привязаны к конкретным полям и строкам, объявляются через live region и
дают способ исправления. Import недоступен, пока preview отсутствует, устарел
после изменения draft или содержит blocking errors.

На tablet layout складывается в одну колонку, но сохраняет табличное
представление и связь `исходная колонка → роль`. На phone страница работает в
compatibility mode:

- показывается неблокирующая рекомендация продолжить на большом экране;
- глобальные параметры складываются в одну колонку, затем идут
  `Источник с ролями → Preview`;
- raw table остаётся таблицей с горизонтальной прокруткой только внутри
  bounded-контейнера: card representation не используется;
- action bar остаётся доступной, резервирует место внизу и не перекрывает
  контент;
- горизонтального overflow всей страницы нет.

Текущие legacy-расхождения, которые нельзя переносить:

- import доступен до authoritative preview;
- preview считает только bounded rows выбранной таблицы, тогда как import может
  затронуть несколько compatible tables;
- повторный import supersede/recreate rows и пока не имеет payload-aware
  idempotency;
- все восемь ролей показаны одновременно;
- table picker из одних номеров не помогает отличить кандидатов;
- zero-based `first_data_row` раскрыт пользователю как внутренний индекс.

## API/application

Добавлено на шаге 4.2:

```text
GET  /api/v1/imports/documents/{document_id}/mapping
POST /api/v1/imports/documents/{document_id}/mapping/preview
```

Остаётся на шаг 4.4:

```text
POST /api/v1/imports/documents/{document_id}/mapping/import
```

Mapping read содержит:

- document identity/status/account/currency;
- capability и blocking reason;
- saved template/default mapping facts;
- bounded table summaries, column candidates и suggestions;
- stable field/warning/error codes.

`table_ref` становится typed identity:

```json
{
  "pageNumber": 1,
  "tableIndex": 0
}
```

API использует видимый 1-based `firstDataRowNumber`; application command
сохраняет внутренний zero-based индекс. Preview request содержит явный mapping
command. Preview остаётся server-side и не создаёт raw rows. Response
ограничивает количество preview rows, но считает полный deterministic scope
всех compatible tables и отдельно возвращает total/valid/invalid counts,
truncation fact и table refs.

Структурно неверный mapping возвращает `422` со stable error/field codes.
Ошибки отдельных строк возвращаются внутри preview как stable row codes.
Browser projection ограничена также по tables, cells и длине текстовых
значений; storage identity и полный raw document не раскрываются.

Import request использует тот же typed command, optional template name и
idempotency key. Он вызывает существующий mapping import use case,
deduplication и document lifecycle. Успех возвращает committed document/review
summary и canonical review target kind.

## Frontend state/UI

Реализовано на шаге 4.3:

- Route: `/app/imports/documents/:documentId/mapping`.
- Mapping draft хранится feature-local отдельно для каждой исходной таблицы;
  server document/table data в draft не копируются.
- Analyzer suggestion заполняет mapping, но остаётся проверяемой подсказкой.
- Desktop workbench использует полную ширину, compact global settings,
  column-local role selectors, bounded raw table и readonly financial preview
  с полным переносимым описанием.
- Core amount strategy явно переключается между одной signed-колонкой и
  отдельными debit/credit колонками.
- Обязательные и дополнительные роли сгруппированы в native select каждой
  исходной колонки.
- Server preview сохраняется при последующих ошибках; изменение draft помечает
  его устаревшим и требует обновления.
- Capability/no-table, pending, validation и network states имеют явный copy.
- Ссылки из списка Imports и карточки документа ведут в canonical React route.

Дополнение 4.3.1 фиксирует направление суммы без явного знака до реализации
idempotent import:

- для single amount mapping пользователь отвечает на вопрос
  `Что означает сумма без знака`;
- доступны понятные действия `Остановить и показать ошибку`,
  `Считать поступлением` и `Считать списанием`;
- явные `+`, `−` и бухгалтерские скобки всегда имеют приоритет над настройкой;
- `Требовать знак` возвращает стабильную row error
  `unsigned_amount_direction_required`, а не молча считает сумму доходом;
- preview агрегирует количество строк с этой ошибкой, связывает предупреждение
  с полем `unsignedAmountDirection` и не показывает успешный badge при наличии
  ошибочных строк;
- действие из предупреждения переводит фокус к настройке, а изменение правила
  снимает contextual highlight и помечает preview устаревшим;
- `MoneyValue` получает числовую часть и валюту раздельно, поэтому исходный
  символ валюты не дублируется рядом с кодом `RUB`;
- analyzer/fallback mappings безопасно начинают с `Требовать знак`;
- сохранённый template хранит правило; старые templates без нового поля
  сохраняют прежнюю семантику `Поступление`;
- split debit/credit mapping определяет знак по роли колонки и не использует
  это правило.
- Выбор table может отражаться в query parameter для Back/Forward, если это
  доказано interaction test; все восемь mapping fields в URL не помещаются.
- Preview не очищает draft при `422`, `409` или network error.
- Import не optimistic и блокирует повторную submit.
- Source table, mapping form и preview имеют раздельную visual hierarchy.
- Desktop использует доступную ширину таблиц; phone сохраняет таблицу в
  bounded horizontal-scroll container без horizontal page overflow.
- Labels/tones/copy принадлежат frontend, warning semantics — server.

## Tests

Backend:

- workspace isolation и management permission;
- document lifecycle/capability;
- typed table identity;
- saved-template ownership;
- all supported column roles;
- duplicate role, missing required role и invalid row errors;
- bounded preview и deterministic row ordering;
- preview не мутирует persistence;
- import создаёт только reviewable raw rows;
- deduplication и idempotent replay;
- template save и conflicting idempotency payload;
- successful transition в existing React review.

Frontend:

- defaults и saved template;
- switching tables;
- all mapping controls and accessible labels;
- draft survives preview/error;
- warnings, candidates и row errors;
- no-table/readonly/stale states;
- pending/repeated import;
- keyboard order, focus, desktop/tablet layout и phone compatibility mode.

Browser:

- single-table suggested mapping;
- multiple-table selection;
- debit/credit mapping;
- amount mapping;
- invalid preview followed by correction;
- optional template save;
- import followed by canonical React review;
- desktop/tablet и phone compatibility mode без page overflow или
  console/request errors.

## Replacement/delete

После gate удалить:

- `routes/mapping.py`;
- `presentation/mapping/*`;
- `templates/imports/mapping.html` и `templates/imports/mapping/*`;
- оставшиеся mapping-only shared imports partials;
- `presentation/field_labels.py` и `mapping_suggestions.py` после consumer search;
- mapping template/presentation tests и selectors.

Historical mapping GET становится query-preserving redirect. Historical preview
и import form POST endpoints удаляются, а не превращаются в постоянную вторую
mutation surface.

## Exit gate

- full unknown-statement mapping работает только в React/API;
- preview и import остаются server-authoritative;
- retry не создаёт raw rows повторно;
- draft/error/back behavior доказаны interaction tests;
- mapping ведёт в существующий canonical React review;
- legacy mapping routes/presentation/templates удалены;
- realistic browser mapping проходит на трёх viewport.
