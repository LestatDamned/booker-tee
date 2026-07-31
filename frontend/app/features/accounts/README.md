# Accounts frontend

Accounts полностью принадлежат React и versioned JSON API:

```text
/app/accounts
  -> GET /api/v1/accounts
  -> account-list-page.tsx

/app/accounts/:accountId
  -> GET /api/v1/accounts/:accountId
  -> account-detail-page.tsx
  -> account settings / imported operation correction
  -> authoritative API response
```

State ownership:

- server владеет workspace checks, balance, capabilities, lifecycle и
  optimistic concurrency;
- URL владеет account identity, filters и pagination;
- route loader владеет загруженным snapshot;
- React component владеет drafts, disclosure, pending/error и последним
  committed snapshot до route revalidation.

Financial mutations не optimistic. Create/update/archive/restore и correction
подтверждаются только committed API response. Historical `/accounts` и
`/accounts/:accountId` остаются query-preserving compatibility redirects;
отдельного Jinja/HTMX Accounts UI больше нет.
