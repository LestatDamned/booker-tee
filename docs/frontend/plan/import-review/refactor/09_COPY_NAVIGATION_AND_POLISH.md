# Этап 9. UX/UI-полировка и сменные темы

Статус: completed 2026-07-23.

Принято: 2026-07-23 по результатам UX/UI-аудита текущей React-страницы.

Этот файл — единый оставшийся execution plan для Import Review UI. Он не
создаёт новое дерево дочерних документов: каждый slice выполняется и принимается
отдельно, а прогресс отмечается здесь.

## Цель

Пользователь должен быстро понять:

1. что произошло в строке выписки;
2. какое решение предлагает система;
3. что мешает проведению;
4. что будет создано после подтверждения;
5. какое одно действие нужно выполнить следующим.

Страница сохраняет форму плотной очереди со встроенным редактированием. Она не
становится CRUD-таблицей, пошаговым wizard или интерфейсом парсера.

## Baseline аудита

Встроенный `review_interactions` audit прошёл на `1440×1000`, `920×900` и
`390×844`: horizontal overflow, browser errors и UX assertion failures не
обнаружены. Значит, основной remaining problem — не техническая
работоспособность, а визуальная иерархия и скорость понимания.

Основные найденные разрывы:

- возможный дубль не показывает сравнение с кандидатом и причину совпадения;
- незавершённая операция может выглядеть как уверенный будущий результат;
- сумма, три badge-роли, источник решения, outcome и действия конкурируют в
  одной строке;
- раскрытый editor слишком длинный на mobile и ослабляет контекст операции;
- по умолчанию показаны все строки вместо основной очереди нерешённых;
- фильтры имеют одинаковый визуальный вес;
- document actions, rules и reconciliation перегружают верх страницы;
- AppShell не показывает полноценный путь к импортам;
- пользовательский текст `Разобрать строку 0` раскрывает внутренний индекс;
- темы уже используют semantic tokens, но живут в одном файле, root theme
  захардкожена, а автоматической проверки контраста нет.

## Принятое направление

Сохраняем основной вариант:

```text
компактный document context
  -> progress + reconciliation + next unresolved action
  -> unresolved-first filters
  -> dense WorkbenchRow queue
  -> one explicit decision / blocking reason per row
  -> inline editor
  -> committed server snapshot
```

Режим одной операции за раз не входит в основной scope. Его можно рассмотреть
позже как дополнительный mobile/focus mode, если реальные пользователи не могут
эффективно работать с очередью.

## Целевая структура страницы

```text
← К документу

Проверка выписки
Основной счёт · statement.xlsx

2 требуют решения · 1 проведена · Сверка не завершена
[Следующая нерешённая]                     [Применить правила]

[Требуют решения 2] [Предложения 1] [Проблемы 0] [Завершённые 1]

01.06.2026                                  −1 234,56 RUB
OZON Маркетплейс
Расход · Продукты
Предложено правилом «OZON»

Предварительный результат: Расход → Продукты
                                      [Проверить предложение]
```

## Контракт строки

### Нерешённая строка

- Одна основная сумма находится в устойчивом месте.
- Описание сильнее secondary facts, но не конкурирует с суммой.
- Финансовый тип, категория и workflow status остаются разными понятиями, но
  не обязаны одновременно выглядеть как три равноценных badge.
- До открытия editor видна одна конкретная причина: `Выберите категорию`,
  `Проверьте возможный дубль`, `Не определена сумма`.
- Primary CTA унифицируется вокруг решения пользователя: `Проверить операцию`,
  `Проверить предложение` или `Проверить перевод`.

### Outcome

- `Предварительный результат` используется, когда операция не подтверждаема.
- `Готово к проведению` используется только при `canConfirm=true`.
- `Проведено` описывает только committed результат.
- Нельзя писать `Будет создан расход`, если обязательная категория или другая
  часть финансового смысла ещё не выбрана.
- Для transfer всегда показывается маршрут `откуда → куда`; незаполненная
  сторона названа явно.

### Возможный дубль

До lifecycle action пользователь видит:

- текущую дату, сумму и описание;
- кандидата: дату, сумму, описание, документ/операцию;
- объяснение совпадения;
- два явных решения: `Это новая операция` и `Отметить дублем`.

Если текущий read model не содержит этих facts, сначала расширяется
workspace-scoped API contract. React не вычисляет duplicate policy.

### Проведённая строка

- Становится визуально спокойнее нерешённой.
- Показывает созданный тип, категорию/маршрут и влияние на счёт.
- Undo и технические данные остаются во вторичном disclosure.

## Mobile contract

Порядок информации:

```text
дата -> описание -> сумма -> предложение/проблема -> primary action
```

- Фильтры не занимают большую сетку: допускается горизонтальный scroll или
  компактный native select с сохранённой семантикой.
- Primary CTA занимает доступную ширину; secondary actions не конкурируют с
  ним.
- Открытый editor сохраняет видимыми описание и сумму текущей операции.
- Итог расположен рядом с confirm action.
- Rule creation и raw comparison закрыты до явного запроса.
- После успешной mutation focus переходит к следующей нерешённой строке.
- Длинное filename не определяет высоту первого экрана.

## Групповые действия и большие документы

- `Применить правила` остаётся безопасным document-level action: оно создаёт
  предложения, но не проводит деньги.
- Bulk confirm не входит в scope: каждое финансовое решение требует явного
  review.
- По умолчанию открывается unresolved queue; terminal rows доступны отдельным
  фильтром.
- Виртуализация или pagination вводятся только после profiler/browser evidence.
  До измерения новая client-state или virtualization library не добавляется.

## Архитектура токенов и тем

Сохраняется действующий контракт:

```text
foundation tokens
  -> raw palette + semantic mapping внутри theme
  -> component CSS Modules используют только semantic tokens
```

Целевая организация:

```text
frontend/app/styles/
  tokens.css
  themes/
    index.css
    catppuccin-mocha.css
    catppuccin-latte.css
    test.css
```

Правила:

- `tokens.css` владеет spacing, typography, radii, control geometry, motion и
  layout constants; тема их не меняет.
- Каждый theme file объявляет свою raw palette и полный набор semantic color
  tokens.
- Component и feature CSS не знают имён Catppuccin и не содержат raw color.
- Тема выбирается одним `data-theme` на root.
- `income`, `expense`, `transfer`, `profit`, `warning` и `danger` сохраняют
  смысл во всех палитрах; status color не подменяет money color.
- Style checker находит theme files автоматически, проверяет полноту token
  contract и запрещает raw palette вне themes.
- Для каждой темы отдельно проверяются contrast pairs: body text `4.5:1`,
  large text/UI boundaries/focus `3:1` и различимость financial states не
  только цветом.
- Theme preference и способ хранения принимаются отдельно от palette split;
  отсутствие switcher не блокирует проверяемый theme contract.

## Переиспользование

Сохраняются существующие `AppShell`, `WorkbenchRow`, `ActionStack`,
`ExpansionPanel`, `Badge`, `MoneyValue`, `Button`, `RequestState`, form fields,
`StatementReconciliation`, server evaluation и focus management.

Допустимые feature-local additions только при подтверждённой необходимости:

- `ReviewQueueToolbar`;
- `ReviewDecisionSummary`;
- `DuplicateComparison`;
- `ReviewItemContext`.

Новая UI library или глобальная state library не требуется.

## Execution slices

Каждый slice требует отдельного подтверждения пользователя и завершается
focused tests, relevant checks и screenshot evidence. Новые plan-файлы не
создаются.

### 9A. Copy и рабочий фильтр

Статус slice: completed 2026-07-23.

- [x] Открывать `Требуют решения` как основной рабочий filter.
- [x] Упростить labels, status, empty/error copy и убрать внутренний row index.
- [x] Сократить повторение source account и технических facts.
- [x] Сохранить counts и `aria-pressed` semantics.

### 9B. Иерархия строки и outcome

Статус slice: completed 2026-07-23.

- [x] Оставить один главный денежный акцент.
- [x] Различить preliminary, ready и committed outcome.
- [x] Показать blocking reason до открытия editor.
- [x] Уменьшить конкуренцию badge, source, outcome и action rail.

### 9C. Duplicate evidence и recovery

Статус slice: completed 2026-07-23.

- [x] Показать сравнение possible duplicate с кандидатом.
- [x] Объяснить причину совпадения без client-owned policy.
- [x] Для network, stale и validation errors показать конкретный recovery path.
- [x] При необходимости расширить API/read model и workspace isolation tests.

### 9D. Компактный editor и mobile

Статус slice: completed 2026-07-23.

- [x] Сохранить контекст текущей операции при длинном editor.
- [x] Сблизить live outcome и confirm action.
- [x] Оставить rule/raw sections progressive.
- [x] Проверить focus, touch targets и отсутствие overflow.

### 9E. Navigation и большие очереди

Статус slice: completed 2026-07-23.

- [x] Добавить путь к импортам и корректный active state в AppShell.
- [x] Сохранять filter/navigation context.
- [x] Переводить пользователя к следующей нерешённой строке после success.
- [x] Измерить большие документы до решения о pagination/virtualization.

### 9F. Theme split и Catppuccin Latte

Статус slice: completed 2026-07-23.

- [x] Разделить theme files без изменения component geometry.
- [x] Добавить Catppuccin Latte как второй production palette contract.
- [x] Перевести financial controls с status tokens на money tokens, где это
      соответствует смыслу.
- [x] Расширить style checker автоматическим discovery и contrast validation.
- [x] Проверить foundation gallery и Import Review в Mocha, Latte и test theme.

## Целевые формулировки

- `Проверить операцию` / `Изменить операцию`;
- `Предварительный результат`;
- `Готово к проведению`;
- `Что мешает подтверждению`;
- `Фрагмент описания`;
- `Применять это решение к похожим строкам`;
- `Следующая нерешённая строка`;
- `Есть необъяснённая разница` только при реальной необъяснённой разнице.

## Definition of Done

- [x] Пользователь за один scan понимает problem, proposed outcome и next action.
- [x] Possible duplicate имеет достаточное evidence для осознанного решения.
- [x] Preliminary UI не обещает создание неподтверждаемой операции.
- [x] В ordinary flow нет parser/internal terminology без пользовательской
      пользы.
- [x] Filters однозначны, unresolved-first и имеют корректные counts/semantics.
- [x] Active navigation видна, но спокойнее рабочей области.
- [x] Component CSS не содержит raw palette и не знает имя темы.
- [x] Mocha, Latte и test определяют полный semantic token contract.
- [x] Contrast, focus, touch targets и reduced motion проверены для каждой темы.
- [x] Нет overflow на `390×844`, `920×900`, `1440×1000`.
- [x] Пройдены format, lint, style, type, feature tests, build и relevant UI
      audit.
- [x] Зафиксирован финальный desktop/tablet/mobile screenshot set для обеих
      production themes.
