# Import Review в React

## Поток данных после Slice 07

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

ImportReviewConfirmationService
  -> POST confirm + expectedStatus + Idempotency-Key
  -> atomic posting/rule/validation/document lifecycle commit
  -> authoritative review snapshot
  -> React reconciliation без optimistic financial state

ImportReviewRuleApplicationService
  -> POST apply-rules
  -> один committed review snapshot
  -> обновление всех sibling suggestions

Browser navigation
  -> /app/imports/documents/{document_id}/review
  -> historical GET временно перенаправляет с сохранением query
```

`ImportReviewReader` возвращает финансовые и lifecycle facts. API переводит
`Decimal` в строки и Python `snake_case` в JSON `camelCase`. React отвечает
только за labels, layout, раскрытие raw details и переход к первой оставшейся
строке.

UI разделён по устойчивым причинам изменения:

- `review-item.tsx` собирает строку, действия и expansion panels;
- `review-item-presentation.tsx` владеет labels, status/outcome mappings и
  lifecycle presentation;
- `source-comparison.tsx` показывает raw и normalized evidence;
- page, row и editor используют отдельные CSS Modules.

Confirm повторно проверяет references и capability внутри server transaction.
`expectedStatus` защищает от stale draft, а `Idempotency-Key` позволяет безопасно
повторить тот же запрос после потери ответа. Это похоже на Python command object
с optimistic concurrency token: локальная форма описывает намерение, но истиной
становится только committed response.

## Владение state

- Database/application: persisted statuses, terminal/reviewable policy, порядок
  и progress queue, raw и normalized source values.
- Route loader: загруженный server snapshot.
- React component: local classification/transfer drafts, pending/error state и
  current server snapshot после мутации. Confirmed financial state появляется
  только из committed API response.
- React Router URL: рабочий `filter` и раскрытый объём очереди `rows`; browser
  Back/Forward восстанавливает navigation context без global store.

Большая очередь сначала рендерит 50 строк и раскрывается блоками по 50 через
`Показать ещё`. Server ordering и payload не меняются; pagination и
virtualization library не вводятся без новых production evidence.

## TypeScript-аналогия для Python-разработчика

`ImportReviewDto` похож на type annotation для Pydantic response, а Zod schema —
на `model_validate()` для неизвестного JSON во время выполнения. Generated type
сам по себе не проверяет network response: TypeScript types исчезают после
компиляции, поэтому boundary выполняет `safeParse()`. Решение и альтернативы
зафиксированы в
[`ADR-0005`](../../../../docs/architecture/decisions/0005-generated-types-and-runtime-validation.md).

Discriminated union `ImportReviewLoadResult` похож на явный набор dataclass
results для success/unauthenticated/forbidden/not-found/error. В отличие от
Python exception flow, TypeScript заставляет component разобрать каждый variant
до доступа к `review`.

## Что намеренно отсутствует

- глобальная cache library и optimistic financial state;
- постоянный второй import-review UI: legacy presentation удалён;
- снятие временного `/app` prefix — это общий routing cleanup Stage 07.
