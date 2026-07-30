# Slice 01: Account List And Create

Статус: planned.

## Outcome

Пользователь открывает `/app/accounts`, видит все workspace accounts с
authoritative balance и создает новый счет, если имеет financial-write
permission.

## API/application

Добавить:

```text
GET  /api/v1/accounts
POST /api/v1/accounts
```

List response содержит:

- ordered account summaries;
- id, name, type, currency, initial balance, active state и mutation token;
- confirmed movement total и authoritative balance;
- page capability `canCreate` + stable readonly reason;
- допустимые account type facts; default currency уже доступна из session.

Repository/application read агрегирует account balance/count одной focused
query или bounded числом queries, не вызывает `get_detail` на каждый account и
не загружает movement rows.

Create request содержит name/type/currency/initialBalance. API переводит decimal
string в `Decimal`; application валидирует workspace permission, normalized
name/currency и фиксирует mutation одной transaction boundary. Success
возвращает committed account summary.

## Frontend state/UI

- Route: `/app/accounts`.
- Loader читает typed runtime-validated response.
- List показывает balance как primary metric, currency отдельно, type и
  active/archive status текстом.
- Create form использует shared fields/error summary/focus conventions.
- Draft остается при `422` или network error.
- Mutation не optimistic; повторный submit блокируется.
- Empty workspace показывает create form владельцу/editor и readonly
  explanation viewer.
- Links в detail до Slice 02 ведут в живой historical detail; list GET
  переключается на React только после собственного gate.

## Tests

Backend:

- workspace isolation и ordering;
- balance/count semantics;
- list не вызывает per-account detail query и не загружает movements;
- viewer/editor capability matrix;
- create validation и Decimal precision;
- create нельзя направить в другой workspace;
- read не делает commit.

Frontend:

- empty/populated/readonly/error states;
- balance formatting без client calculation;
- accessible type/status text;
- create success и committed row;
- draft survives validation/network error;
- focus first invalid field и repeated-submit guard;
- desktop/tablet/mobile geometry.

## Replacement/delete

После gate:

- historical `GET /accounts` становится query-preserving redirect;
- list branch/template/list-only tests удаляются;
- legacy `POST /accounts` удаляется после JSON create gate;
- detail routes/templates пока остаются до Slice 02+.

## Exit gate

- canonical shell Accounts link открывает React list;
- create доступен только по server capability;
- list API не имеет N+1 full-ledger behavior;
- historical list GET только redirect, historical create POST отсутствует;
- desktop/tablet/mobile browser flow проходит.
