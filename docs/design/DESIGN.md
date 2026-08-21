# Booker Tee design

Статус: действующий UI/UX contract.

Booker Tee — тёмный, спокойный, плотный и точный financial workbench. Интерфейс
должен помогать проверять деньги, а не выглядеть как marketing dashboard.

## Иерархия

1. Money и outcome.
2. Description и business context.
3. Account, category, property и source.
4. Technical identifiers только по запросу.

Одна страница имеет одну основную задачу и одно primary action. Destructive и
редкие действия отделяются. Progressive disclosure скрывает детали, но не
последствия финансовой команды.

## Financial presentation

- Используйте server-formatted currency и `MoneyValue`.
- Income/expense/transfer различаются текстом и структурой, не только цветом.
- Transfer показывает обе стороны и не выглядит как income/expense.
- Status всегда имеет текстовую метку.
- Empty, loading, stale, error и retry states видимы и честны.
- Raw/import uncertainty не маскируется декоративной уверенностью.

## Page composition

Обычная рабочая страница состоит из `PageFrame`, `PageHeader`,
workspace context, toolbar/filters, primary content surface и request state.
Для плотных коллекций переиспользуйте workbench components; feature CSS владеет
только уникальной раскладкой и финансовым смыслом.

Filters имеют draft и explicit applied URL state. Selected record должен иметь
deep link. После mutation сохраняйте понятный контекст, focus и возможность
безопасного retry.

## Forms and actions

Используйте native input/select/textarea/radio внутри shared `Field`/
`Fieldset`. Общая композиция отвечает за label, hint, error, section/grid,
summary и actions; feature владеет полями, draft, request mapping и business
wording.

Validation показывается возле поля и в linked summary. Первая ошибка получает
focus только после submit. Destructive action требует явного confirmation с
названием объекта и последствием. Не создавайте schema-driven universal form.

## Responsive and accessibility

- Workflow должен работать на 1440, 920, 390 и 320 px без horizontal overflow.
- Mobile сохраняет primary action, money, status и consequences.
- Keyboard user может пройти navigation, filters, forms, dialogs и row actions.
- Focus visible во всех themes; dialogs возвращают focus.
- Icon-only control имеет accessible name.
- Status/action не кодируются одним цветом.
- Motion уважает `prefers-reduced-motion`.

## Visual system

Используйте semantic CSS variables, themes и CSS Modules. Не импортируйте legacy
global CSS и не добавляйте Tailwind/shadcn или второй token system. Новые tokens
появляются только для повторяющейся семантики.

Перед новой страницей откройте
[`UI_FOUNDATION.md`](UI_FOUNDATION.md), существующий похожий workflow и
`/app/foundation`. Props и фактическое поведение определяются кодом и tests.
