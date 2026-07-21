# Slice 05: Duplicate и Lifecycle

Статус: completed.

## Реализовано

- Чистая domain-policy `ImportReviewLifecyclePolicy` владеет допустимыми
  переходами для persisted status и отдельно запрещает mutation уже связанной
  строки. React получает только `allowedActions`, а не повторяет матрицу.
- Typed application command требует `expectedStatus`, блокирует строку и
  документ, различает idempotent replay и stale command, обновляет validation и
  синхронизирует document lifecycle в одной транзакции.
- `mark_unique` переводит possible duplicate в `MATCHED`, но не исключает такую
  несвязанную строку из queue и не мешает её последующему posting.
- API возвращает полный authoritative review snapshot. Stale state имеет
  стабильный `409 import_review_lifecycle_conflict`, недопустимый переход —
  `422`, scoped missing item — `404`.
- React показывает только разрешённые server actions, запрашивает явное
  подтверждение для duplicate/ignore, не меняет financial state optimistically
  и умеет перечитать строку после конфликта с восстановлением focus.
- Legacy status action переведён на ту же policy; legacy route и шаблоны
  сохранены до replacement gate Slice 07.

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

Gate пройден: domain matrix и replay/stale покрыты тестами, application test
проверяет завершение и повторное открытие документа, API/React tests проверяют
authoritative reconciliation, readonly, `409`, `422`, danger confirmation и
focus. Browser audit проверяет lifecycle action рядом с classification panel.

Completed: 2026-07-21

Implemented: domain lifecycle policy, transactional application command,
versioned API mutation, React actions и legacy parity.

Checks run: scoped Python format, full lint/type/tests, все frontend gates,
production build и UI audit.

Intentional deviations: mutation возвращает полный review snapshot вместо
дельты строки — это минимальная уже существующая feature-local consistency
граница без новой cache abstraction.

Cleanup performed: `MATCHED` удалён из legacy final-status shortcut; linked
`MATCHED` по-прежнему отображается как persisted terminal state.

Learning notes updated: не требовалось — в slice не появился новый общий
React/TypeScript concept.
