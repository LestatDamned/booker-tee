# Slice 05: Duplicate и Lifecycle

Статус: planned.

## Результат

Пользователь разрешает possible duplicate как unique, duplicate, ignored или
needs review и может восстановить допустимые states через явное поведение,
проверяемое server.

## Vertical scope

- Ввести typed review actions и allowed-transition policy на основании текущих
  persisted status/link state.
- Явно разрешить неоднозначность `MATCHED`: `mark_unique -> MATCHED` остается в
  review queue и postable до confirmed/ignored/duplicate.
- Отклонять forged transitions из confirmed/linked/failed states вместо надежды
  на скрытые UI actions.
- Возвращать authoritative row, queue, validation и document lifecycle updates.
- Оставить danger confirmation copy и размещение menu в React.

## Тесты

- transition matrix, включая stale/replayed commands;
- possible duplicate -> unique остается reviewable;
- confirmed/link state нельзя перезаписать raw status action;
- queue/document completion и validation refresh после ignore/duplicate;
- readonly, `409`, `422`, focus и sibling reconciliation.

## Exit gate

Lifecycle rules имеют одного server owner, а значения queue/document больше не
противоречат друг другу между Presenter, repository и application code.
