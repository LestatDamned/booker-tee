# Import Review в React

## Поток данных Slice 01

```text
ImportReviewReader
  -> GET /api/v1/import-review/{document_id}
  -> generated OpenAPI type + Zod runtime validation
  -> React Router clientLoader
  -> ImportReviewPage
```

`ImportReviewReader` возвращает финансовые и lifecycle facts. API переводит
`Decimal` в строки и Python `snake_case` в JSON `camelCase`. React отвечает
только за labels, layout, раскрытие raw details и переход к первой оставшейся
строке.

## Владение state

- Database/application: persisted statuses, terminal/reviewable policy, порядок
  и progress queue, raw и normalized source values.
- Route loader: загруженный server snapshot.
- React component: в этом read-only slice нет собственной копии server state;
  `<details>` и URL fragment используют встроенное browser state.

## TypeScript-аналогия для Python-разработчика

`ImportReviewDto` похож на type annotation для Pydantic response, а Zod schema —
на `model_validate()` для неизвестного JSON во время выполнения. Generated type
сам по себе не проверяет network response: TypeScript types исчезают после
компиляции, поэтому boundary выполняет `safeParse()`.

Discriminated union `ImportReviewLoadResult` похож на явный набор dataclass
results для success/unauthenticated/forbidden/not-found/error. В отличие от
Python exception flow, TypeScript заставляет component разобрать каждый variant
до доступа к `review`.

## Что пока намеренно отсутствует

- classification и confirmability;
- category/transfer panels и local drafts;
- mutations, optimistic financial state и cache library;
- redirect или удаление legacy import review.
