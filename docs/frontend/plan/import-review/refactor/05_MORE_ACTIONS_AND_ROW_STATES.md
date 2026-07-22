# Этап 5. Дополнительные действия и состояния строк

Статус: completed.

## Цель

Убрать тяжёлые вторичные блоки и сделать состояния очереди различимыми без
одновременной окраски строки по нескольким признакам.

## Scope

- Компактное disclosure `Ещё действия`.
- В меню: lifecycle, ignore, technical source и другие редкие действия.
- Danger actions отделены визуально и требуют понятного подтверждения.
- Confirmed строки спокойнее; problem строки получают signal; открытая строка
  получает working accent.
- Financial direction остаётся в сумме и type badge, workflow state — в другом
  визуальном канале.

## Критерии готовности

- [x] Основные действия видимы без раскрытия меню.
- [x] Transfer не спрятан в меню.
- [x] Confirmed, suggestion, review, problem и working различимы.
- [x] Цвет не является единственным признаком состояния.
- [x] Disclosure работает с клавиатуры и имеет корректные ARIA-атрибуты.

## Реализовано

- `Подтвердить`, `Изменить` и открытие основного редактора остаются видимыми;
  lifecycle, ignore, undo posting и исходные данные собраны в `Ещё действия`.
- Меню стало компактным floating disclosure и больше не увеличивает высоту
  action rail; на mobile его ширина ограничена viewport.
- Danger-группа отделена разделителем и явной подписью `Опасные действия`;
  destructive mutations сохраняют подтверждение и focus management.
- После отмены или успешного действия меню закрывается и не перекрывает
  соседние строки.
- Технические raw/normalized данные вынесены из classification editor в
  отдельную полноширинную панель `Исходные данные строки N`.
- `WorkbenchRow` получил независимый workflow channel: `settled`,
  `suggestion`, `review`, `problem`; раскрытая строка использует `working`.
- Workflow-state сопровождается текстовым status badge или problem signal,
  поэтому цвет не является единственным носителем смысла.
- Working accent переведён с цвета прибыли на нейтральный accent интерфейса.

## Проверки

- frontend tests: 121 passed;
- TypeScript, ESLint, style check и Prettier: passed;
- production build: passed;
- UI audit: 51 маршрут на `1440×1000`, `920×900` и `390×844`, passed;
- keyboard activation native `summary/details` проверена в Chromium audit;
- screenshots: `/tmp/booker-import-review-stage5-complete/`.
