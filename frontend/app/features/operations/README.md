# Operations frontend

`/app/operations` — canonical React collection всех денежных событий workspace.

Текущий slice переиспользует проверенный manual-ledger workbench, URL state,
filters, pagination, rows и manual create workflow. Unified API client добавляет
runtime validation для `source`, typed provenance и server capabilities.

На Stage 4 `operation_id` открывает один source-aware `ExpansionPanel`.
Manual-команды остаются manual-only, imported correction переиспользует
существующую ограниченную форму и endpoint, debt ведёт в owning workflow, system
остаётся read-only. UI выбирает mutation по server-owned `editKind`, а не выводит
разрешение из source.

```text
route loader -> GET /api/v1/operations -> shared collection workbench
                                      -> manual commands for editKind=manual
                                      -> imported correction for editKind=imported
                                      -> provenance links for import/debt
```

URL владеет search, type, source, period, references, pagination и
`operation_id`. Новая global state или отдельная CSS foundation не используется.

Stage 5 добавляет один `operationHref()` для переходов из Activity, account
ledger, Reports, debt payment history, Import Review и manual create. Backend DTO
передаёт только UUID; React route не сохраняется в audit payload или финансовой
read model.

Stage 6 сделал этот slice единственным browser/read потоком. Старый
`/app/ledger/manual` только сохраняет query при redirect; отдельный loader и
`GET /api/v1/manual-ledger` удалены. Source-specific manual command API остаётся
в manual-ledger feature и подключается только по server-owned capabilities.
