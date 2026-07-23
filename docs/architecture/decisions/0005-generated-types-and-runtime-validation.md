# ADR-0005: Generated Types And Runtime Validation

Status: accepted 2026-07-23.

## Context

FastAPI OpenAPI describes the compile-time API contract and generates
`frontend/app/api/generated/schema.ts`. TypeScript types disappear at runtime,
so they cannot prove that an HTTP response actually matches that contract.

The migrated Session, Manual Ledger and Import Review boundaries additionally
use handwritten Zod schemas. This duplicates the response shape, but detects
malformed, stale or unexpected JSON before it enters component state. Generating
runtime validators from OpenAPI was considered, as was relying on TypeScript
alone.

## Decision

- FastAPI Pydantic schemas and exported OpenAPI remain the source of truth.
- `openapi-typescript` remains the compile-time DTO generator.
- `npm run api:check` must compare a fresh backend export with the committed
  generated TypeScript file.
- External JSON stays `unknown` until a focused Zod schema validates it.
- Runtime schemas are owned by the API boundary that consumes them and are
  constrained with `z.ZodType<GeneratedDto>`.
- Runtime validation covers response data used by the frontend; it does not
  reproduce backend business validation or financial policy.
- A runtime-schema generator is not introduced now. It may be reconsidered if
  schema maintenance becomes a measured source of repeated defects across more
  migrated workflows.

## Consequences

- Compile-time drift and runtime payload mismatch are detected by different,
  explicit gates.
- Some structural duplication remains, but it is local to API adapters and
  checked against generated DTOs by TypeScript.
- Backend contract changes require regenerating types and updating the relevant
  runtime validator and tests.
- Components receive validated DTOs and do not parse network data themselves.
