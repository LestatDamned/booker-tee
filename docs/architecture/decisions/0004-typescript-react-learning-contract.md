# ADR-0004: TypeScript And React Learning Contract

Status: accepted 2026-07-20.

## Context

Владелец проекта — Python-разработчик, изучающий JavaScript, TypeScript и React
на этой миграции. Технически корректный, но непрозрачный frontend не считается
maintainable.

## Decision

- TypeScript `strict` включен с первого commit.
- Необоснованные `any`, type assertions и non-null assertions запрещены.
- API input считается `unknown` до contract validation/narrowing.
- Data flow, state ownership и async states выражаются явно.
- Function components и composition являются default; hooks извлекаются по
  самостоятельной ответственности.
- `useEffect` синхронизирует внешнюю систему, а не хранит derived state.
- Dependencies и abstractions добавляются для доказанного риска, не как набор
  модных frontend practices.
- Каждый нетривиальный slice сопровождается объяснением request/state/render
  flow, использованных concepts, Python-аналогии и места, где аналогия ломается.
- `frontend/README.md` содержит запуск и один end-to-end code walkthrough.
- `frontend/docs/typescript-for-python.md` является живым справочником только по
  используемым в проекте concepts.
- Production comments объясняют причины и ограничения; учебник синтаксиса живет
  в focused docs и handoff.

## Consequences

- Review оценивает explainability наравне с build и tests.
- Clever generic abstraction отклоняется, если явный feature code легче понять.
- Новая библиотека требует короткого объяснения problem, alternatives и cost.
- Учебная документация обновляется вместе с первым реальным использованием
  concept, а не создается заранее как полный курс JavaScript.

## Reference

- [TypeScript `strict`](https://www.typescriptlang.org/tsconfig/strict.html)
