# Slice 04 — Archive and restore

Статус: planned; blocked by README decision D2 и зависит от D1/D3.

## User outcome

Writer архивирует больше не используемый объект или восстанавливает его,
понимая последствия. История не удаляется; UI обновляет status/view только
после committed response и даёт понятный recovery при conflict/failure.

## Application/API

```text
POST /api/v1/properties/{property_id}/archive
POST /api/v1/properties/{property_id}/restore
```

Lifecycle request содержит expected status/`updatedAt`. Server возвращает
summary snapshot либо stable 404/409/422. Capabilities определяются server;
client не выводит action только из status.

До реализации зафиксировать D2. Рекомендуемый минимальный contract:

- archive сохраняет linked operations и не меняет их reports;
- archived Property исчезает из новых active choice lists;
- existing transaction rules не отключаются скрыто;
- confirmation честно сообщает эти последствия;
- server может вернуть impact facts/reason codes, но counts не вычисляются в
  browser;
- restore очищает `archived_at` и возвращает объект в active lists.

## React interaction

- archive — отдельное lifecycle действие, визуально подчинённое edit/create;
- impact confirmation использует `ConfirmationDialog`, initial focus на cancel;
- pending относится только к выбранной row и предотвращает repeat;
- success переносит row между accepted lifecycle views и показывает Toast;
- failure остаётся рядом с collection/row через `InlineNotice` + «Повторить»;
- conflict предлагает reload/retry authoritative state;
- restore может быть непосредственным reversible action, если согласованный
  impact не требует confirmation.

## Financial regression tests

- archive/restore workspace isolation и stale conflict;
- archived object не входит в active Manual Ledger/Import Review/Chat/rule form
  options;
- historical linked confirmed operations остаются linked и продолжают
  корректно входить в property reports;
- transfer с Property по-прежнему не влияет на profit/ROI;
- accepted D2 behavior для existing active rule зафиксирован отдельным test;
- no hard delete/cascade operation mutation.

## Exit gate

- D2 не остаётся неявным;
- lifecycle API/UI и cross-feature regression suite проходят;
- SSR lifecycle остаётся доступен до Slice 05.

