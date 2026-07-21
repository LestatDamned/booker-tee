# Slice 03: Classification, Category и Property

Статус: planned.

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
