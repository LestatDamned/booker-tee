# Users module

`users` owns human identity and authentication. It does not own financial data.
Financial data belongs to `Workspace` through workspace-scoped models.

The broader production plan for identity, sessions, shared workspaces,
invitations, permissions, and Telegram readiness lives in:

```text
src/app/features/workspaces/README.md
```

## Responsibilities

- Store user identity fields.
- Normalize unique email addresses.
- Hash and verify passwords.
- Create and revoke web sessions.
- Resolve a session into a user.
- Later, link external identities such as Telegram.

## Story

Read this module as the identity part of a request.

```text
credentials, session cookie, or external identity
-> User
-> UserSession
-> hand off to workspaces for membership and current workspace
```

`users` answers "who is this person?". It does not answer "which financial data
can this person touch?". That second question belongs to `workspaces`.

## Code should read like a story

Working code is not enough. Identity code is ready only when it is easy to read,
safe to reuse, and obvious to extend. A developer should be able to open the
registration, login, or logout use case and read it as a product story:

```text
normalize identity input
-> validate credentials
-> create or resolve User
-> create or revoke UserSession
-> hand off to workspaces when a workspace is needed
```

Good code shape:

```python
async def login(command: LoginCommand) -> LoginSession:
    email = normalize_email(command.email)
    user = await users.require_active_by_email(email)
    verify_user_password(command.password, user.password_hash)

    workspace = await workspaces.require_first_active_workspace(user.id)
    session = await sessions.create_for_user(user.id, workspace.id)
    await transaction.commit()
    return LoginSession(user=user, workspace=workspace, session=session)
```

Bad code shape:

```python
async def handle_auth(data: dict[str, Any]) -> Any:
    account = await get_account(data)
    state = await process(account, data, action="login")
    return await finish(state)
```

Quality bar:

- The happy path is visible.
- Validation has explicit function names.
- Password and session operations are named honestly.
- No financial access checks are hidden here.
- Reusable identity rules are extracted once.
- Session side effects are obvious.
- Tests describe the same story as the code.

## File size and split rules

Keep files small enough that a use case can be read without scrolling through
unrelated behavior.

Soft limits:

```text
models.py          can be larger, but only persistence definitions
repository.py      about 150-220 lines per focused repository
service.py         about 150-220 lines before extracting use cases
router.py          about 150-220 lines before splitting route groups
commands.py        small dataclasses/Pydantic command objects
```

When `service.py` grows, split by identity story:

```text
users/application/
  registration.py
  login.py
  logout.py
  sessions.py
  external_identities.py
```

When `repository.py` grows, split by aggregate:

```text
users/repositories/
  users.py
  sessions.py
  external_identities.py
```

When `router.py` grows, split by UI/API surface:

```text
users/routes/
  auth.py
  profile.py
  external_identities.py
```

Split when a file starts telling more than one story. Do not split only for
architecture theater.

## Function shape rules

- Keep public service methods named as use cases.
- Prefer command objects over loose dictionaries.
- Avoid `data`, `payload`, `result`, `item`, and `obj` when a domain name exists.
- Avoid boolean flag parameters; create two functions instead.
- Keep password hashing, session token hashing, and CSRF helpers explicit.
- Keep workspace membership logic out of `users`.
- Keep routers free of identity business rules.

## Boundaries

- Do not attach accounts, operations, imports, categories, properties, or reports
  directly to `User`.
- Use user ids for audit fields only.
- Use `WorkspaceContext` for financial actions.
- Keep database queries in `repository.py`.
- Keep business rules in `service.py`.
- Keep HTTP, forms, redirects, and templates in `router.py`.

## Reuse rules

Reusable identity rules should be small, explicit, and domain-named:

```text
normalize_email
clean_user_name
validate_password
hash_password
verify_password
hash_session_token
```

Do not hide workspace access checks in `users`. Resolve identity here, then pass
control to `workspaces`.

## Production readiness checklist

- Registration is atomic with personal workspace creation.
- Sessions are stored hashed, expire, and can be revoked.
- Login rejects inactive users.
- Logout revokes the current session.
- Tests cover signup, login, logout, duplicate email, and inactive users.
- Telegram identities are linked through a separate model, not by overloading
  user profile fields.
