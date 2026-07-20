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
