# Workspace collaboration

Статус: базовый multi-user workflow, адресные invitations, role capabilities,
единый manager-only журнал administrative/financial activity, explicit limits,
repository/API/chat isolation, PostgreSQL concurrency gate и локальный two-user
browser smoke реализованы и проверены. Реальная SMTP-доставка остаётся production
rollout gate.

Workspace — строгая граница финансовых данных. Collaboration не
создаёт второй ledger или отдельный team backend: несколько
пользователей работают с теми же workspace-scoped entities через
общие application services и repositories.

```text
React workspace UI
  -> /api/v1/workspaces/*
  -> workspace application service
  -> permission policy + workspace-scoped repository
  -> PostgreSQL
```

## Что уже работает

- создание, directory и переключение workspace;
- membership с ролями и активным/отключённым статусом;
- приглашение на конкретный verified email, email delivery, accept и revoke;
- изменение роли, disable/reactivate, self-leave;
- атомарная передача ownership;
- deactivate/restore workspace с fallback sessions;
- optimistic concurrency, row locks и idempotency для опасных
  transitions;
- workspace audit events для administrative mutations;
- React экраны workspace directory, settings, members и invitations;
- отдельный owner/admin activity timeline с URL-фильтрами, safe typed projection,
  entity links и keyset pagination;
- различимый доступ всех шести ролей: analyst не получает raw import data,
  viewer читает её без mutation, team directory доступен только owner/admin;
- session capabilities управляют React navigation, но сервер повторно проверяет
  каждую raw/team boundary.

## Цель укрепления

Довести collaboration до надёжного сценария малой команды:

1. каждая выдаваемая роль имеет отличимый и тестируемый смысл;
2. owner/admin видит на отдельной странице значимые administrative и financial
   mutations с persisted actor;
3. simultaneous mutations не перезаписывают чужие изменения;
4. workspace isolation подтверждена для всех browser/API/chat
   boundaries;
5. лимит малой команды явный, а не молчаливое обрезание списка.

## Границы

Этот план не включает:

- realtime presence, WebSocket и live cursors;
- comments, mentions и review assignments;
- произвольные custom roles и permission builder;
- organisation hierarchy и groups;
- cross-workspace movements и consolidated workspaces;
- PostgreSQL RLS при текущем single-backend access model;
- background queue только ради invitation email.

Эти capabilities появляются только после подтверждённого product scenario.

## Документы

- [`EMAIL_BOUND_INVITATIONS.md`](EMAIL_BOUND_INVITATIONS.md) — адресные
  invitations, delivery, accept и membership recovery;
- [`ROLE_CAPABILITIES.md`](ROLE_CAPABILITIES.md) — каноническая
  permission matrix и смысл `analyst`;
- [`ACTIVITY_AND_AUTHORSHIP.md`](ACTIVITY_AND_AUTHORSHIP.md) — единый manager-only
  журнал значимых administrative и financial actions;
- [`COLLABORATION_HARDENING.md`](COLLABORATION_HARDENING.md) — isolation,
  concurrency, explicit limits и security gates;
- [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) — порядок vertical slices,
  проверки и exit gates.

Общий runtime contract остаётся в
[`src/app/features/workspaces/README.md`](../../../src/app/features/workspaces/README.md),
а общие architecture и financial invariants — в
[`docs/architecture/ARCHITECTURE.md`](../../architecture/ARCHITECTURE.md) и
[`docs/domain/DOMAIN_MODEL.md`](../../domain/DOMAIN_MODEL.md).

Stage 4 implementation обязана следовать принятым constraints из
[`ACTIVITY_AND_AUTHORSHIP.md`](ACTIVITY_AND_AUTHORSHIP.md): transactional append,
узкий activity writer/repository, explicit replay outcome, typed/versioned payload
и отсутствие event bus/outbox без external consumer.
