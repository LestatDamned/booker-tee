# Users and workspaces notes

`users` отвечает за локальную идентичность человека. `workspaces` отвечает за
финансовую границу данных: личные финансы, семья, бизнес, объект или проект.

Текущий MVP пока не реализует настоящую авторизацию. Вместо этого пользователь
и workspace выбираются локально через cookie:

```text
booker_user_id
booker_workspace_id
```

Это осознанный промежуточный шаг: он позволяет тестировать реальные
workspace-границы без преждевременной сложности логина, паролей, приглашений и
RBAC UI.

## Product flow

```text
create user
-> create personal workspace
-> choose current user/workspace
-> all financial pages use WorkspaceContext
```

## Boundaries

- `User` не владеет финансовыми данными напрямую.
- `Workspace` остается основной границей для счетов, операций, импортов,
  категорий, объектов, отчетов и правил.
- `WorkspaceMember` связывает пользователя и workspace.
- `get_current_workspace_context()` должен возвращать пользователя и workspace,
  доступный этому пользователю.

## Deferred

Позже этот слой можно заменить настоящей auth-сессией. Тогда cookie выбора
workspace останется полезной, а cookie выбора пользователя исчезнет.
