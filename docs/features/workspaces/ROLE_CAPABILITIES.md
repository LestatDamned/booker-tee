# Workspace role capabilities

Статус: реализовано 10 августа 2026; automated backend/API/React gates пройдены.

## Цель

Роль — стабильный product preset, а не произвольный набор permissions.
Сервер вычисляет capabilities и повторно проверяет их на mutation/read
boundary. React не выводит права из названия роли.

Текущая матрица различает write/import/member/workspace actions, но
`analyst` и `viewer` фактически совпадают. Целевой contract делает
`analyst` узкой read-only ролью без доступа к raw import sources.

## Канонические роли

### Owner

Единственный authoritative owner workspace.

- все read/write/import/member capabilities;
- workspace identity, currency и lifecycle;
- ownership transfer;
- не может leave/disable до ownership transfer.

### Admin

Управляет данными и командой, но не workspace identity/lifecycle.

- read/write/import capabilities;
- invitations и members в пределах admin policy;
- workspace activity journal;
- не может назначать/менять admin и owner;
- не может deactivate/restore workspace или менят default currency.

### Editor

Ведёт финансовые данные.

- все financial reads;
- manual ledger, reference data, debts и financial corrections;
- import upload/review/mapping;
- не управляет members, invitations и workspace settings.

### Uploader

Добавляет и готовит импорты, но не меняет ledger вне import workflow.

- financial reads и raw import access;
- upload, mapping и review preparation;
- posting допустим только через текущий server import policy;
- не создаёт manual operations и не меняет reference data;
- не управляет team/workspace.

### Analyst

Анализирует derived financial data без доступа к source documents.

- dashboard, reports, balances и confirmed ledger reads;
- categories/properties как report dimensions;
- не видит uploaded files, raw extracted text/tables, mapping preview и
  import review payloads;
- не изменяет financial data;
- не управляет team/workspace.

### Viewer

Полный read-only observer workspace.

- dashboard, reports, accounts, ledger, debts и reference data;
- import documents, raw/review details и source metadata;
- не изменяет financial data;
- не управляет team/workspace.

Viewer — более широкий доступ, чем analyst. Роли не образуют линейную
иерархию: uploader может делать import actions, которые analyst/viewer не
могут.

## Permission matrix

| Capability                  | Owner |        Admin | Editor | Uploader | Analyst | Viewer |
| --------------------------- | ----: | -----------: | -----: | -------: | ------: | -----: |
| Read dashboard/reports      |   yes |          yes |    yes |      yes |     yes |    yes |
| Read accounts/ledger/debts  |   yes |          yes |    yes |      yes |     yes |    yes |
| Read raw imports/review     |   yes |          yes |    yes |      yes |      no |    yes |
| Write manual financial data |   yes |          yes |    yes |       no |      no |     no |
| Manage imports              |   yes |          yes |    yes |      yes |      no |     no |
| Manage reference data/rules |   yes |          yes |    yes |       no |      no |     no |
| Read members/invitations    |   yes |          yes |     no |       no |      no |     no |
| Manage members/invitations  |   yes | yes, bounded |     no |       no |      no |     no |
| Read workspace activity     |   yes |          yes |     no |       no |      no |     no |
| Manage workspace/lifecycle  |   yes |           no |     no |       no |      no |     no |
| Transfer ownership          |   yes |           no |     no |       no |      no |     no |

`disabled`, `removed` и `pending` membership не дают ни одной capability независимо
от role.

## Backend design

Чистая policy остаётся в `features/workspaces/permissions.py`. Не вводится
generic permission engine, database ACL table или custom role builder.

Существующие predicates сохраняются. Добавляются только реально
недостающие distinctions:

```python
def can_view_raw_import_data(membership: WorkspaceMember) -> bool:
    return has_active_role(
        membership,
        {
            WorkspaceRole.OWNER,
            WorkspaceRole.ADMIN,
            WorkspaceRole.EDITOR,
            WorkspaceRole.UPLOADER,
            WorkspaceRole.VIEWER,
        },
    )


def can_view_member_directory(membership: WorkspaceMember) -> bool:
    return has_active_role(
        membership,
        {WorkspaceRole.OWNER, WorkspaceRole.ADMIN},
    )


def can_view_workspace_activity(membership: WorkspaceMember) -> bool:
    return can_view_member_directory(membership)
```

API dependencies оборачивают predicates в stable error codes. Application services,
которые могут вызываться не только из HTTP, повторно применяют
ту же pure policy к actor membership.

## Session and API capabilities

Session DTO не должен расти до сотен action flags. В нём достаточно
стабильных navigation-level flags:

```text
canReadWorkspace
canWriteFinancialData
canManageImports
canViewRawImportData
canViewMemberDirectory
canManageMembers
canViewWorkspaceActivity
canManageWorkspace
```

Entity response по-прежнему возвращает entity-specific capabilities. Например,
`canManageImports=true` не означает, что любой document можно delete или любую
raw row можно confirm.

## Route enforcement

Read boundaries делятся по смыслу:

- dashboard/reports/accounts/ledger/debts/reference reads требуют active
  workspace read;
- import document list/detail, raw payload, mapping и review reads дополнительно
  требуют `can_view_raw_import_data`;
- member/invitation directory требует `can_view_member_directory`;
- activity требует `can_view_workspace_activity`;
- mutation остаются на существующих financial/import/member/workspace
  policies.

Важно: закрытие React navigation не заменяет route dependency. Прямой
API request от analyst к raw import возвращает `403 raw_import_read_forbidden`.

## React contract

- shell/navigation строится из session capabilities;
- route loader обрабатывает server `403`, даже если navigation устарела;
- workspace member role select использует только server
  `assignableRoles`;
- UI объясняет role простым языком, включая отличие Analyst
  от Viewer;
- после смены собственной role/status или workspace switch выполняется
  hard navigation, чтобы не сохранять старые данные и capabilities.

## Privacy decisions

- member emails и pending invitation emails видят только owner/admin;
- non-manager не получает member directory DTO целиком;
- analyst не получает storage metadata, raw text/tables и source file download;
- masked account values не заменяют workspace authorization;
- role не меняет financial invariants: editor/admin/owner не могут
  сделать transfer profit-affecting или parser-confirmed.

## Tests and exit gate

- pure matrix test покрывает каждую role и inactive statuses;
- API tests доказывают, что analyst не читает import list/detail,
  mapping и review;
- viewer читает те же surfaces, но не мутирует их;
- uploader проходит import workflow, но не manual/reference mutations;
- editor меняет finance/import data, но не team/workspace;
- admin management не затрагивает owner/admin targets за пределами
  current policy;
- owner-only settings/lifecycle/transfer остаются owner-only;
- React navigation и controls совпадают с server capabilities;
- direct forbidden API requests и stale-session UI покрыты отдельно.

Slice complete only when role matrix проверена на каждом активном API
surface, а не только в `permissions.py`.

## Реализованный route inventory

| Surface                                                     | Read boundary           | Mutation boundary                                        |
| ----------------------------------------------------------- | ----------------------- | -------------------------------------------------------- |
| dashboard, reports, accounts, ledger, debts, reference data | active workspace read   | financial write                                          |
| import documents, mapping, review                           | raw import read         | import management; posting также требует financial write |
| members, invitations                                        | member directory read   | member/invitation policy                                 |
| workspace settings and lifecycle                            | actor/target membership | workspace/member policy                                  |
| session                                                     | active workspace read   | —                                                        |

Activity API использует target-scoped `can_view_workspace_activity`; owner/admin
получают typed history, остальные active roles — `403`, foreign workspace —
privacy-safe `404`.

Automated evidence:

- pure matrix покрывает все шесть ролей и `pending`/`disabled`/`removed`;
- analyst получает `403 raw_import_read_forbidden` до вызова raw reader;
- viewer читает documents/mapping/review, но mutation остаются запрещены;
- editor/uploader/analyst/viewer получают `403 member_directory_forbidden`
  без member/invitation DTO и email;
- React скрывает Imports по server capability и показывает безопасный forbidden
  state при устаревшей ссылке/сессии.
