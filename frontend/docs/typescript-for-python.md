# TypeScript и React для Python-разработчика

Это не полный учебник. Здесь описаны только concepts, уже используемые в
Booker Tee Stage 01.

## Module и import

Каждый `.ts`/`.tsx` файл — module. `import type` существует только для type
checker и исчезает из JavaScript build. Это похоже на import под
`if TYPE_CHECKING`, но TypeScript стирает все типы при компиляции.

`.tsx` означает, что module может содержать JSX — HTML-подобное описание React
дерева. JSX не является template string и компилируется в вызовы JavaScript.

## TypeScript type не равен Pydantic

`SessionDto` сгенерирован из OpenAPI и проверяет наш код при сборке. Browser
может получить любой JSON, поэтому `response.json()` рассматривается как
`unknown`. Zod schema проверяет payload во время выполнения, примерно как
`SessionApiResponse.model_validate(payload)` в Pydantic.

Граница аналогии: TypeScript type не существует в runtime и сам ничего не
валидирует. Pydantic model существует и выполняет validation в Python process.

## Discriminated union

`SessionLoadResult` перечисляет допустимые состояния:

```ts
type Result =
  | { status: "loading" }
  | { status: "authenticated"; session: SessionDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };
```

Ближайшая Python-аналогия — несколько dataclass/Pydantic models с
`Literal["..."]` discriminator. После проверки `result.status` TypeScript знает,
какие поля доступны. Поэтому невозможно случайно прочитать `session` у error.

## Function component и props

`SessionShell({ result })` — обычная функция, получающая props и возвращающая
React tree. При новых props/state React вызывает её снова. Component не должен
изменять финансовые данные во время render.

Props похожи на типизированные параметры Python-функции. Отличие: React владеет
жизненным циклом вызовов, а returned JSX описывает желаемый UI, не пошаговые DOM
операции.

## useState

`useState` хранит локальное состояние component между render. Setter не меняет
переменную на месте: он просит React выполнить новый render с новым значением.
Это ближе к immutable state transition, чем к присваиванию атрибута Python
object.

## useEffect

В Stage 01 effect синхронизирует component с внешней системой — HTTP API. Он не
вычисляет derived UI state. Cleanup flag не позволяет завершившемуся запросу
обновить component после unmount.

Эффект не запускается при Docker prerender, поэтому session конкретного
пользователя не попадает в статический `index.html`.

## Generated DTO и handwritten model

Generated schema принадлежит transport contract и может быть перезаписана.
Handwritten union `SessionLoadResult` принадлежит UI: он добавляет loading,
unauthenticated и error semantics, которых нет в successful API DTO. Не следует
использовать generated OpenAPI namespace прямо во всех components.

## CSS custom properties и темы

`--color-bg-surface` — runtime CSS value. Один и тот же component получает
разное значение из ближайшего `data-theme`, поэтому тема меняется без нового
React render и без ветвления TypeScript-кода.

Ближайшая Python-аналогия — конфигурация, переданная через context. Граница
аналогии: CSS custom property участвует в cascade браузера и наследуется по DOM,
а не передаётся как явный аргумент функции.

Semantic token называет роль (`--color-status-danger`), а не оттенок (`red-400`).
Raw palette разрешена только в отдельных файлах `app/styles/themes/`. Их
`index.css` подключает Mocha, Latte и контрастную test theme, а style checker
автоматически проверяет общий semantic contract и WCAG contrast pairs.
Component CSS использует роли, поэтому новая тема не копирует geometry.

## CSS Modules

Файл `button.module.css` компилирует локальные class names. Import `styles`
похож на Python module namespace: `styles.button` явно показывает владельца.
Однако CSS всё ещё участвует в cascade через tokens и global foundation;
изоляция class name не превращает stylesheet в полностью изолированный object.

## Props union и composition

`RequestStateProps` — union, который запрещает невозможные комбинации вроде
`loading=true` одновременно с `error=true`. Это аналог нескольких dataclass с
Literal discriminator.

`WorkbenchRow` принимает `aside`, `meta` и `expansion` как React nodes. Feature
собирает устойчивые области через composition вместо наследования или одного
универсального класса с десятками boolean-настроек. В отличие от Python
inheritance, child content не переопределяет методы: React просто строит единое
дерево из переданных nodes.

## ref и управление focus

`useRef<HTMLButtonElement>` хранит ссылку на конкретный DOM button между render,
не вызывая новый render при изменении ссылки. Gallery использует ref, чтобы
после закрытия expansion вернуть keyboard focus к кнопке «Редактировать».

Это отдалённо похоже на сохранённую ссылку на Python object. Отличие: React
назначает DOM node во время commit и очистит `ref.current` при unmount; читать и
менять DOM через ref следует только для imperative задач вроде focus, а не для
обычного UI state.

## Route client loader

`clientLoader` у route получает browser `Request`, загружает server state и
передаёт результат route component как `loaderData`. Ближайшая Python-аналогия —
FastAPI route dependency, которая готовит данные до вызова основного обработчика.

Граница аналогии: loader выполняется в browser, повторяется при client-side
navigation и не является доверенной backend boundary. Финансовые permissions и
workspace isolation всё равно повторно проверяет FastAPI.

В manual ledger loader передаёт query string URL в `/api/v1/manual-ledger`.
Поэтому применённые filters и pagination принадлежат URL, переживают refresh и
могут быть скопированы другому пользователю с доступом к тому же workspace.

## Transport DTO и UI model

`ManualLedgerListResponse` генерируется из OpenAPI и описывает JSON-контракт.
`toManualOperationRowModel()` — явный frontend adapter, похожий на Python
presenter: он переводит domain values в labels, semantic tones и display money.

Component не получает generated DTO напрямую. Благодаря этому `WorkbenchRow`
не знает backend statuses, а backend не возвращает CSS class, готовую кнопку или
Jinja ViewModel. Для transfer mapper читает явный `operationType`; знак decimal
string не используется для угадывания финансового смысла.

## Controlled filter draft и applied URL state

`ManualLedgerFilters` хранит редактируемый draft в `useState`. Пока пользователь
пишет описание или выбирает счёт, URL и загруженный список не меняются. Это
похоже на Python form object, который ещё не передан query service.

После `Применить` draft сериализуется в query string, `page` сбрасывается на `1`,
а React Router повторно вызывает `clientLoader`. С этого момента URL становится
applied state и единственным источником для server request. `key={location.search}`
создаёт новый экземпляр filter component после navigation, поэтому новый draft
инициализируется уже из нормализованного URL.

Граница аналогии: `useState` не изменяется синхронно как атрибут Python object.
Setter планирует новый render. Поэтому сериализация выполняется из текущего
state в submit handler, а не чтением DOM вручную.

## Form composition: аналогия с Python

`Field`, `Fieldset`, `FormSection`, `FormGrid` и `FormActions` — маленькие
компоненты разметки. Они похожи на хорошо именованные Python-функции, которые
задают общий протокол, но не знают бизнес-сценарий. Например, `Field` связывает
label, hint и error, однако не знает, что `amount` является денежной суммой.

Feature-компонент `ManualOperationFields` явно собирает эти части и хранит
условие `operationType === "transfer"`. Поэтому бизнес-ветвление видно в одном
месте, а повторяющиеся CSS и accessibility rules не копируются.

Radio button — controlled input немного другого вида:

```tsx
<input
  checked={draft.operationType === "expense"}
  onChange={() => setDraft({ ...draft, operationType: "expense" })}
  type="radio"
/>
```

`checked` здесь играет ту же роль, что `value` у text input. Объект
`{ ...draft, operationType: "expense" }` создаёт новый объект из старых полей с
одной заменой; он не мутирует существующий draft. Это ближайший аналог
`dataclasses.replace(draft, operation_type="expense")`.

`fieldset` и `legend` — не декоративные обёртки. Browser и screen reader
понимают, что несколько radio controls отвечают на один вопрос. CSS Grid только
раскладывает поля и не должен менять их DOM-порядок.

При server validation `FormErrorSummary` объявляет общую ошибку и даёт ссылки на
поля, а inline error остаётся рядом с control. Это две разные задачи: быстро
сообщить, что submit не удался, и объяснить, как исправить конкретное значение.

## Route splitting и отдельный loader module

Production build React Router делит route module на отдельные chunks: код
`clientLoader` может загружаться отдельно от component. Поэтому нетривиальную
реализацию loader мы импортируем из `manual-ledger-loader.ts`, а в route оставляем
тонкую функцию-адаптер.

Ближайшая Python-аналогия — вынести dependency в отдельный importable module,
когда framework загружает endpoint и presentation разными workers. Обычный
unit-тест функции проверяет контракт, но только production build и browser test
доказывают, что bundler действительно включил зависимость в client chunk.

## Controlled mutation form

`ManualOperationCreate` хранит draft и состояние отправки рядом с формой. Draft —
обычный typed object в `useState`; request state — discriminated union
`idle | pending | error`. Поэтому TypeScript не позволяет случайно прочитать
`fieldErrors`, пока форма не находится в error state.

Submit handler сначала переводит форму в `pending`, затем отправляет JSON с CSRF
header. Ответ `201` ещё не добавляется в список вручную: React Router переходит
на URL с `operation_id`, повторно запускает loader и получает authoritative
server list. Ответ `422`, наоборот, не заменяет draft и только добавляет ошибки
к соответствующим controls.

Python-аналогия — Pydantic form model плюс явный enum состояния запроса. Граница
аналогии: setter React не меняет объект немедленно, а планирует render; кроме
того, disabled button защищает UI от concurrent click, но не является backend
idempotency guarantee против сетевого replay.

Когда форма получила transfer, generated OpenAPI contract стал discriminated
union из двух объектов: income/expense request и transfer request. Общий
`operationType` позволяет TypeScript сузить объект: у transfer доступны
`sourceAccountId`/`destinationAccountId`, а у другой ветки — `accountId`,
`categoryId` и `propertyId`. Это близко к Pydantic discriminated union: одна
внешняя JSON-граница, но невозможные сочетания полей не становятся моделью.

Значение нативного `<select>` в DOM всё равно
имеет широкий тип `string`, поэтому `operationType()` явно сужает его до
union. Это runtime-проверка, а не `as`-утверждение компилятору «поверь мне».

Python-аналогия — преобразование внешней строки в `Literal`/Enum на границе до
создания Pydantic command. Благодаря этому остальной draft и API request уже не
могут содержать произвольный operation type.

## Idempotency key и retry

Форма создаёт UUID один раз для нового draft и отправляет его в
`Idempotency-Key`. Ошибка `422` или сетевой сбой не меняют ключ: повторная
отправка относится к той же попытке создания. После успешного ответа или
явной отмены создаётся новый UUID.

Backend хранит ключ вместе с fingerprint команды и уникализирует его внутри
workspace. Тот же ключ и тот же payload возвращают уже созданную operation;
тот же ключ с другим payload даёт `409`. Уникальный индекс также закрывает гонку
двух одновременных запросов, которую невозможно надёжно решить disabled-кнопкой.

Python-аналогия — UUID в command плюс unique constraint и повторное чтение после
`IntegrityError`. Граница аналогии: React state здесь нужен не для финансовой
логики, а чтобы идентичность попытки пережила новые renders и пользовательский
retry.

## Lazy edit: snapshot и draft

`ManualOperationEdit` не получает тяжёлую форму из list response. После открытия
правой рабочей панели `useEffect` запускает GET edit snapshot, а `useRef`
отмечает, что запрос уже был начат внутри текущего экземпляра формы. Закрытие
панели размонтирует форму; следующее открытие намеренно получает свежую версию.

Состояние edit panel — discriminated union: `idle`, `loading`, `load_error` или
`ready`. Только ветка `ready` содержит одновременно server snapshot, изменяемый
draft, reference options и submission state. TypeScript заставляет проверить
ветку перед чтением этих полей.

Python-аналогия — объект результата загрузки с разными dataclass-вариантами.
Граница аналогии: `useEffect` описывает синхронизацию React-компонента с внешним
HTTP-сервисом; это не аналог вызова функции непосредственно во время render.

Create и edit используют один `ManualOperationFields` и один
`ManualOperationDraft`. Они не делят lifecycle: create владеет idempotency key,
а edit — загруженной `version` и server snapshot. Переиспользуется стабильная
форма данных, а не случайно похожий orchestration code.

При `422` backend errors добавляются к текущему draft. При `409` draft тоже
остаётся нетронутым, пока пользователь явно не нажмёт «Загрузить актуальную
версию». Только это действие заменяет draft свежим snapshot.

Python-аналогия optimistic concurrency — отправить `expected_version` из формы
и выполнить SQL `UPDATE` с version check. Disabled-кнопка предотвращает второй
локальный submit, но именно server version не позволяет двум вкладкам молча
перезаписать изменения друг друга.

## Lifecycle action как маленький state machine

`ManualOperationLifecycle` получает не произвольный URL, а union
`"cancel" | "restore"`. Доступное действие приходит из server capabilities:
confirmed operation показывает cancel, ignored operation — restore. Frontend не
пытается самостоятельно решить, разрешён ли переход.

Локальное состояние компонента — union `idle | pending | conflict | error`.
В `pending` блокируется только нажатая lifecycle-кнопка, остальные строки списка
остаются рабочими. Успешный POST возвращает полную новую operation; этот server
response немедленно заменяет строку, а route revalidation затем сверяет весь
список с backend.

Каждая команда отправляет текущую `version`. Поэтому capability — это подсказка
для UI, но не разрешение на запись: backend снова проверяет workspace, роль,
исходный status и version. При `409` компонент предлагает явно обновить строку.

Python-аналогия — маленький объект команды с `Literal` action и optimistic lock.
Главное отличие: TypeScript union ограничивает код клиента на этапе компиляции,
но доверенная проверка перехода всё равно принадлежит Python use case.

## Destructive confirmation и удаление из коллекции

Удаление вынесено в `ManualOperationDelete`, потому что его lifecycle отличается
от обратимых cancel/restore. State union содержит отдельную ветку `confirming`:
первое нажатие не отправляет HTTP-запрос, а показывает последствия и две явные
кнопки. Только «Да, удалить» переводит компонент в `pending` и вызывает DELETE.

Успешный DELETE возвращает `204 No Content`, поэтому frontend не пытается читать
JSON. Callback передаёт `operationId` владельцу списка, который иммутабельно
добавляет id в набор скрытых строк. Если удалённая строка была URL target,
`operation_id` и hash убираются через navigation с сохранением filters.

Python-аналогия — удалить элемент из новой копии коллекции по id, а затем
перечитать страницу из repository. React сначала reconciles локальную коллекцию,
чтобы UI ответил немедленно, а route revalidation подтверждает pagination и
total с backend. При `409` строка не исчезает и предлагает обновить snapshot.

## Mutation lock, focus и retry

Одна строка manual ledger владеет `mutationPending` для edit, lifecycle и delete
действий. Поэтому редактор раскрывается внутри этой строки и использует тот же
локальный lock. Форма create находится выше — в page-level `WorkbenchPanel` — и
сообщает о pending-состоянии странице через `onPendingChange`.

Python-аналогия — короткоживущий lock у одного aggregate instance. Граница
аналогии: React lock улучшает UX и предотвращает обычный двойной click, но не
защищает данные сам по себе. Create по-прежнему опирается на idempotency key, а
edit/lifecycle/delete — на server version.

После `422` React сначала рендерит `aria-invalid` и текст ошибок, затем
`useEffect` выполняет императивный `focus()` первого невалидного control. Effect
нужен именно после render: до него элемента с новым состоянием ошибки в DOM ещё
нет. После явной отмены focus возвращается на disclosure-кнопку, чтобы keyboard
пользователь не потерял рабочий контекст.

Сетевой сбой не сбрасывает draft, idempotency key или загруженную version.
Повторное нажатие отправляет ту же логическую попытку, тогда как успешный ответ
заменяет snapshot данными backend. Это похоже на повтор команды после
`ConnectionError`: клиент не делает вывод, применена ли команда, только из факта
разрыва соединения.

## Состояние следует за областью действия

Страница хранит три разных вида состояния отдельно:

```ts
const [createOpen, setCreateOpen] = useState(false);
const [filtersOpen, setFiltersOpen] = useState(false);
const [editingOperationId, setEditingOperationId] = useState<string | null>(
  null,
);
```

Python-аналог — два `bool` и `str | None`. Они разделены не случайно: создание —
page-level dialog, фильтры — состояние коллекции, редактирование принадлежит
конкретной строке. Один общий `panel.kind` создавал бы ложное впечатление, что у
этих задач одинаковая геометрия и одинаковые правила.

Сравнение `editingOperationId === operation.id` передаёт `isEditing` только одной
строке. Строка рендерит editor через `WorkbenchRow.expansion`, поэтому форма
остаётся рядом с датой, суммой и описанием изменяемой операции. `WorkbenchPanel`
по-прежнему отвечает за dialog semantics создания, а строка — за закрытие своего
editor и возврат focus. Это тот же принцип владения состоянием, что и в Python:
состояние должно находиться у объекта с подходящей областью ответственности.
