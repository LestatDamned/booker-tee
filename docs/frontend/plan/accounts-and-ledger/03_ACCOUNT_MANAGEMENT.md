# Slice 03: Account Management

Статус: planned.

## Outcome

Пользователь с financial-write permission меняет настройки счета, архивирует и
восстанавливает его из React detail. Viewer видит account без mutation controls.

## Pre-implementation characterization

До публикации mutation API зафиксировать server tests для:

- изменения currency у account с существующими MoneyEntry/import documents;
- изменения initial balance и влияния на current balance;
- archive/restore при связанных historical данных;
- повторной и stale mutation.

Если существующее поведение допускает финансово некорректную currency mutation,
исправление policy входит в server slice и документируется отдельно; React не
копирует небезопасное поведение.

## API/application

Добавить:

```text
PUT  /api/v1/accounts/{account_id}
POST /api/v1/accounts/{account_id}/archive
POST /api/v1/accounts/{account_id}/restore
```

Update request содержит:

- name, type, currency, initialBalance;
- `expectedUpdatedAt` или эквивалентный explicit application stale token.

Lifecycle request содержит expected active state либо другой явный transition
guard. Server повторно загружает workspace-owned account, проверяет permission,
policy и stale state внутри transaction. Conflict возвращает stable `409`;
field validation — `422`; inaccessible entity — `404`.

Success возвращает committed account header/summary и capabilities, достаточные
для detail reconciliation. Browser не меняет balance или active state
optimistically.

## Frontend state/UI

- Settings draft feature-local и не смешивается с filter URL.
- Current server snapshot не копируется в долгоживущий global store.
- Expected validation/conflict/network error не очищает draft.
- `409` предлагает reload/review current values, а не silently overwrite.
- Archive требует confirmation и объясняет, что history не удаляется.
- Restore является явной lifecycle action.
- Pending блокирует duplicate submit и несовместимые controls.
- После success используется committed snapshot и route revalidation.

## Tests

Backend:

- workspace/permission matrix;
- validation и Decimal precision;
- current balance после initial balance update;
- currency policy с existing dependencies;
- archive сохраняет operations/documents/history;
- archived account остается readable;
- stale update и invalid lifecycle возвращают `409`;
- transaction rollback при failure.

Frontend:

- viewer readonly state;
- draft/error summary/focus;
- update/archive/restore pending and success;
- confirmation keyboard behavior;
- stale conflict recovery;
- committed balance/state reconciliation;
- responsive settings panel/dialog.

## Replacement/delete

После gate удалить historical:

```text
POST /accounts/{account_id}
POST /accounts/{account_id}/archive
POST /accounts/{account_id}/restore
```

Удалить settings-only Jinja/selector/tests после consumer search.

## Exit gate

- только JSON API меняет account;
- stale mutation не перезаписывает более новое состояние;
- archive/restore не удаляют financial history;
- viewer не получает write capability;
- settings browser flow проходит desktop/tablet/mobile.
