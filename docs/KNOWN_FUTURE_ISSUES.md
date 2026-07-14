# Known Future Issues

This file tracks confirmed issues that should not be forgotten, but whose fix
is outside the current refactoring scope.

Add an issue here only when:

- the problem is real and confirmed;
- fixing it would expand the current task too much;
- keeping a large diagnostic laboratory for it is not worth the maintenance
  cost;
- the issue is important enough to revisit later.

Do not add hypothetical ideas, small TODOs, migration history, or already fixed
problems.

When an issue is fixed, mark it resolved with the fixing commit/PR or remove
it if the surrounding context is no longer useful. Delete temporary diagnostic
fixtures that only existed for the resolved issue.

## UI / HTMX

### Stale response overwrite between different HTMX triggers

Status: Open

Priority: Medium/High

Discovered during: CSS/UI refactoring

Problem:

Different HTMX triggers that share one target can issue concurrent requests.
Responses are applied in completion order, so an older slow response can
overwrite a newer faster response.

Confirmed behavior:

- different triggers with the same target run in parallel;
- observed `max_concurrency = 2`;
- a fast newer response can apply first;
- a late older response can overwrite the newer result;
- `hx-disabled-elt` on one clicked button does not stop another trigger that
  targets the same element.

Affected candidates:

- transaction-rule filters/reset/pagination;
- report sort controls;
- shared row targets;
- some panel/lazy-load scenarios.

Why deferred:

- this is a behavioral/request architecture problem, not required for the
  current CSS architecture cleanup;
- read-only requests and mutations need different policies;
- a global fix could introduce surprising cancellation or stale UI behavior;
- feature-specific ownership should be decided before adding synchronization.

The original broad diagnostic fixtures were removed during UI harness cleanup.
Recreate a focused test when implementing request coordination.

Possible future directions:

- `hx-sync`;
- latest-wins policy;
- abort previous request;
- target/group coordination;
- feature-specific request policy;
- server-side idempotency for mutations where relevant.

Do not:

- claim same-trigger `hx-disabled-elt` solves this;
- add broad global synchronization without feature analysis;
- treat read-only sorting/filtering and mutating row actions as the same
  problem;
- keep large permanent visual fixtures only to remember this issue.
