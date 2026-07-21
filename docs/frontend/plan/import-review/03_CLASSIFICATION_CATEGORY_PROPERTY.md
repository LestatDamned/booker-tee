# Slice 03: Classification, Category и Property

Статус: completed.

## Результат

Writer понимает server classification, выбирает category/property, при
необходимости создает category и не теряет незавершенный draft строки при
локальной навигации между panels или validation errors.

## Vertical scope

- Перенести приоритет classification в typed pure domain/application resolver.
- Добавить server-owned confirmability capability и стабильные blocking reason
  codes.
- Обеспечить real-category policy на confirm command boundary; скрытый UI-control
  не является financial-integrity или authorization guard.
- Отдавать workspace-scoped category/property references и rule suggestions.
- Оставить `ready_to_confirm` вычисляемым в API/frontend read projection; не
  добавлять его в `RawTransactionStatus`.
- По необходимости добавить action-specific JSON contracts для выбора/создания
  category; не публиковать legacy wide form command.
- Сохранять draft при `422`, network error и переключении panel; переводить focus
  к первому invalid field.

## Тесты

- приоритет: supported explicit draft, rule suggestion, amount inference,
  unknown;
- блокировка missing/uncategorized/cross-workspace category;
- workspace boundary и optional behavior для property;
- rule suggestion никогда не выполняет silent confirm;
- readonly и draft/error/focus component behavior.

## Exit gate

React не реализует заново classification или confirmability rules, а crafted
request не может обойти category safety policy.

## Реализовано

- Pure domain resolver закрепляет приоритет `explicit → suggested → inferred →
  unknown`; server confirmability возвращает стабильные blocking reason codes.
- Typed GET contract содержит classification, selection, confirmability,
  rule-suggestion facts и workspace-scoped active category/property references.
  Read endpoint по-прежнему не выполняет seed/commit и не зависит от legacy
  Presenter.
- Side-effect-free draft evaluation принимает только operation type,
  category/property IDs и повторно проверяет workspace references. Cross-workspace
  category/property возвращают typed `422`, а не доверяются client options.
- Создание category вынесено в отдельный JSON command. Response содержит только
  новую reference; React добавляет ее в options всех строк и выбирает в текущем
  draft.
- Local row draft переживает закрытие panel, network error и `422`. При field
  error focus переходит к первому invalid control; financial state не обновляется
  optimistic.
- Existing posting boundary больше не подставляет `uncategorized` при crafted
  confirm request: income/expense import требует реальную workspace category.
- Rule suggestion отображается как предложение и никогда не вызывает silent
  confirm. Confirm/post UI остается вне scope этого slice.

Проверки: classification/application/API tests, real-category posting regression,
83 frontend tests, production build и Playwright audit раскрытого panel на
1440/920/390 прошли.
