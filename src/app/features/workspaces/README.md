# Workspaces runtime boundary

Workspace is the ownership and authorization boundary for financial data.

- Application services own membership, invitations, role changes, ownership
  transfer, activation and transaction boundaries.
- Repositories scope every entity by workspace or a validated owned parent.
- Domain policy defines role capabilities and transition rules.
- Session capabilities guide React navigation, but server checks remain
  authoritative.
- Invitation lookup does not reveal account or membership existence.
- Concurrent dangerous transitions use optimistic version or row locks.
- Activity records store typed, privacy-safe details with the financial/admin
  mutation transaction.

The product/security contract is
[`docs/features/workspaces/README.md`](../../../../docs/features/workspaces/README.md).
