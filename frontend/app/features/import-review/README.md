# Import Review в React

## Поток данных Slice 01–04

```text
ImportReviewReader
  -> GET /api/v1/import-review/{document_id}
  -> generated OpenAPI type + Zod runtime validation
  -> React Router clientLoader
  -> ImportReviewPage

ImportReviewTransferService
  -> POST discriminated transfer command + Idempotency-Key
  -> committed current/cross-document review snapshots
  -> feature-local reconciliation
```

`ImportReviewReader` возвращает финансовые и lifecycle facts. API переводит
`Decimal` в строки и Python `snake_case` в JSON `camelCase`. React отвечает
только за labels, layout, раскрытие raw details и переход к первой оставшейся
строке.

## Владение state

- Database/application: persisted statuses, terminal/reviewable policy, порядок
  и progress queue, raw и normalized source values.
- Route loader: загруженный server snapshot.
- React component: local classification/transfer drafts, pending/error state и
  current server snapshot после мутации. Confirmed financial state появляется
  только из committed API response.

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

- duplicate/lifecycle actions;
- обычный confirm/post для income и expense;
- глобальная cache library и optimistic financial state;
- redirect или удаление legacy import review.
