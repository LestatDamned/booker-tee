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
`SessionResponse.model_validate(payload)` в Pydantic.

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
Raw palette разрешена только в `themes.css`. Component CSS использует роли,
поэтому новая тема не копирует geometry.

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

## Route splitting и отдельный loader module

Production build React Router делит route module на отдельные chunks: код
`clientLoader` может загружаться отдельно от component. Поэтому нетривиальную
реализацию loader мы импортируем из `manual-ledger-loader.ts`, а в route оставляем
тонкую функцию-адаптер.

Ближайшая Python-аналогия — вынести dependency в отдельный importable module,
когда framework загружает endpoint и presentation разными workers. Обычный
unit-тест функции проверяет контракт, но только production build и browser test
доказывают, что bundler действительно включил зависимость в client chunk.
