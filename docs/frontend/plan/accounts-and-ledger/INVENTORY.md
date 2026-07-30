# Inventory: Accounts And Account Ledger

Статус: active inventory; list/create replacement completed.

Проверено: 2026-07-30.

## Scope

В migration scope:

```text
GET  /accounts                                      compatibility redirect
POST /accounts                                     removed

GET  /accounts/{account_id}
POST /accounts/{account_id}
POST /accounts/{account_id}/archive
POST /accounts/{account_id}/restore

GET  /accounts/{account_id}/operations/{operation_id}/review-fields/edit
POST /accounts/{account_id}/operations/{operation_id}/review-fields
```

В scope также входят canonical links, account-specific Jinja presentation,
HTMX behavior, selectors, template/presenter tests и UI audit scenarios.

Не входят:

- Manual Ledger create/edit/lifecycle;
- Import Review posting/undo;
- reports calculations;
- redesign account persistence beyond a required explicit stale-state guard;
- multi-currency conversion или consolidated cross-currency total;
- bank synchronization, external account providers или masked account data UX;
- removal of the global `/app` prefix.

## Наблюдаемый flow

### Account list

- Счета упорядочены: active раньше archived, затем по creation time.
- Каждый item показывает name, type, active/archive status, authoritative
  balance, currency, movement count и link в detail.
- Баланс визуально различает positive/negative/zero.
- Editor видит create form; viewer видит тот же список без mutation surface.
- Empty state ведет к create form и вторично к upload, если разрешен import.
- Create принимает name, type, three-letter currency и initial balance.

Текущий router получает список accounts, затем вызывает полный
`AccountLedgerReader.get_detail(...)` для каждого. Это N+1 и дополнительно
загружает первые movement rows, хотя list использует только balance/count.
Replacement обязан использовать focused summary query.

Slice 01 заменил этот list read focused aggregate projection через
`GET /api/v1/accounts`; legacy list template и create POST удалены.

### Account detail

- Header показывает name, type, currency, balance, initial balance и количество
  совпавших проводок.
- Archived account остается доступным.
- Filters: period, search, status, source, operation type, category, property,
  per-page и page.
- Status по умолчанию — `confirmed`; фильтры и pagination находятся в URL.
- Authoritative balance не зависит от list filters.
- Entries отсортированы по operation date, creation/id и money-entry order.
- Empty filtered result отличается только текстом от отсутствия проводок.

### Movement presentation

- Amount является account-relative signed movement.
- Income/expense/transfer/adjustment имеют различимые states.
- Transfer показывает source/destination route и пометку «не влияет на
  прибыль».
- Income/expense показывает category, property, account и status.
- Important non-confirmed statuses и missing category имеют badges.
- Manual operation ведет в существующий React Manual Ledger target.
- Imported operation ведет к source row/review, если raw link доступен.
- System operation readonly.

### Account settings

- Editor меняет name, type, currency и initial balance.
- Editor архивирует active account и восстанавливает archived account.
- Текущий SSR не имеет явного optimistic concurrency token для Account.
- Изменение initial balance влияет на authoritative balance, поэтому новый JSON
  mutation contract обязан иметь stale-state guard.

### Imported operation correction

- HTMX лениво загружает form для confirmed imported operation.
- Form меняет только description, category и property.
- Operation обязана принадлежать workspace и иметь MoneyEntry текущего account.
- Correction разрешен только для `BANK_PDF` + `confirmed`.
- `expected_version` защищает от конкурентного изменения.
- Success заменяет movement row; manual operation редактируется в Manual Ledger.

## Existing application/domain boundary

Сохраняются и переиспользуются:

- `AccountService` validation и account lifecycle behavior, при необходимости
  с выделением явного application transaction owner;
- `AccountRepository` workspace-scoped account lookups;
- `LedgerRepository` account entry, count и balance queries;
- `AccountEntryFilters`, `LedgerPagination`, `LedgerPage`;
- `ImportedOperationReviewUseCase`;
- `imported_operation_actions(...)`;
- Manual Ledger и Import Review canonical routes;
- financial/domain tests для balance, transfer и optimistic operation version.

Текущие `AccountDetailPresenter`, account ViewModels и Jinja templates являются
legacy adapters, а не API contract. `AccountLedgerReader` прямо документирован
как read model legacy screen; его полезные query semantics сохраняются, но DTO
и mapping должны стать application/API-oriented до React consumption.

## Новые read projections

### Directory projection

Одна workspace-scoped query/projection должна вернуть:

- account id/name/type/currency/initial balance/active state/updated timestamp;
- confirmed entry total;
- authoritative balance;
- movement count, семантика которого явно совпадает с list copy;
- page-level create capability и stable readonly reason.

Directory read не загружает `Operation`, raw transaction или первые 50
movements для каждого account.

### Detail projection

Detail read должен вернуть:

- account facts и current mutation token;
- authoritative current balance;
- paginated account-relative movements;
- matched count и pagination facts;
- filter options с stable identities/active facts;
- page и per-movement capabilities/reason codes;
- typed source link facts: manual operation, import row/document или readonly.

API mapping преобразует Decimal в string и snake_case в camelCase. Frontend
строит labels, tones и route URLs.

## Data exposure decisions

Browser DTO может содержать:

- id, name, type, currency, initial balance, active state;
- balance, movement counts и pagination;
- operation id/version/date/type/status/source/description;
- account-relative amount;
- category/property/account references;
- raw transaction id и uploaded document id только для product deep link;
- capabilities и stable blocking reason codes.

Без отдельной задачи не публикуются:

- `account_number_fingerprint`;
- `external_ref`;
- storage identifiers или raw document payload;
- ORM timestamps, кроме `updatedAt`, если он является mutation token;
- audit/user ids без пользовательского consumer.

## Geometry baseline

До Slice 01 снять baseline существующих `/accounts` и одного realistic account
detail для `1440×1000`, `920×900`, `390×844`.

Replacement сохраняет:

- balance как основную метрику;
- ясную active/archive маркировку;
- компактный registry вместо dashboard cards;
- читаемый account header и доступные filters;
- account-relative amount, description и classification в каждой movement row;
- отсутствие horizontal page overflow;
- формы и confirmation controls без перекрытия контента.

Account list и movements могут использовать table/compact-row representation
на desktop и stacked rows на phone. Нельзя переносить legacy geometry
механически, если shared React workbench primitives уже выражают ту же задачу.

## Security and financial invariants

1. Account list/detail фильтруются по current workspace.
2. Operation дополнительно проверяется через account-owned MoneyEntry текущего
   workspace.
3. Не различать чужой и отсутствующий account в browser error contract.
4. Viewer получает read projection без write capabilities.
5. Current balance включает только confirmed entries независимо от detail
   status filter.
6. Transfer movement меняет account balance, но `affects_profit=false`.
7. Archive не удаляет account, MoneyEntry или import history.
8. Archived account не становится доступным для новых операций/import только
   из-за client-side выбора.
9. Account update revalidates name/currency/money and stale token server-side.
10. Imported correction не меняет amount/date/type/status/money entries.

## Cross-feature consumers

Runtime links и scenarios найдены в:

- `frontend/app/shell/app-shell.tsx`;
- `frontend/app/features/import-upload/import-upload-page.tsx`;
- legacy `base.html`;
- authenticated home quick actions;
- dashboard summary/account rows;
- reports account links;
- onboarding checklist;
- workspace return-path/auth tests;
- `scripts/ui_audit.py`;
- generated OpenAPI schema.

До миграции dashboard/reports остаются SSR, но их links должны вести в
canonical React account routes после соответствующего gate.

## Legacy implementation/delete manifest

Удалить после полного replacement:

- account GET/POST/HTMX handlers из `src/app/features/accounts/router.py`;
- `src/app/features/accounts/presentation/detail/`;
- `src/app/templates/accounts/index.html`;
- `src/app/templates/accounts/detail.html`;
- `src/app/templates/accounts/detail/*`;
- account template/presenter tests без runtime consumer;
- account-only CSS selectors после consumer search;
- historical account HTML operations из generated OpenAPI;
- account-specific Alpine/HTMX behavior и UI audit selectors.

Сохранить:

- `models.py`, repository и application/domain behavior;
- migrations и database constraints;
- financial/application tests;
- API/React replacement tests;
- narrow compatibility GET redirects;
- shared legacy CSS только при конкретном remaining SSR consumer.

## Known risks

1. List N+1 может быть случайно воспроизведен в новом application mapper.
2. Detail GET сейчас seed-ит default categories через commit; API read должен
   стать side-effect free.
3. Account update не имеет optimistic integer version.
4. Изменение currency существующего account с entries может нарушить
   историческую согласованность; server policy должна быть явно
   охарактеризована до публикации JSON mutation.
5. Archive capability для account с active workflow dependencies пока
   минимальна; React не должен изобретать дополнительные ограничения.
6. Category/property inactive options должны отображаться достаточно, чтобы
   существующая correction не теряла persisted reference.
7. Большой ledger требует server pagination; client virtualization не заменяет
   bounded API.
