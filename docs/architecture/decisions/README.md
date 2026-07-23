# Architecture Decision Records

Короткие решения, определяющие React migration. Детальная целевая архитектура и
delete gates находятся в
[`REACT_FRONTEND_DESIGN.md`](../../design/REACT_FRONTEND_DESIGN.md).
Порядок реализации и current stage находятся в
[`frontend/plan`](../../frontend/plan/README.md).

Статусы:

- `accepted` — решение действует;
- `superseded` — заменено более новым ADR;
- `proposed` — требует подтверждения перед реализацией.

| ADR | Status | Decision |
| --- | --- | --- |
| [`0001`](0001-react-spa-runtime-and-tooling.md) | accepted | React SPA runtime, npm и same-origin deployment |
| [`0002`](0002-versioned-json-api-boundary.md) | accepted | Versioned JSON API, session/CSRF и generated types |
| [`0003`](0003-tokenized-css-and-themes.md) | accepted | Semantic tokens, themes, CSS Modules и geometry baseline |
| [`0004`](0004-typescript-react-learning-contract.md) | accepted | Понятный TypeScript/React как часть maintainability |
| [`0005`](0005-generated-types-and-runtime-validation.md) | accepted | Generated DTO и runtime validation выполняют разные проверки API boundary |

Новый ADR создается только для решения с реальной альтернативой и заметными
последствиями. Обычные implementation details остаются рядом с кодом.
