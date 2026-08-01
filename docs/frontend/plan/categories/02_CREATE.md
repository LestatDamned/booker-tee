# Slice 02: Create category

Статус: `planned`.

## Outcome

Writer создаёт custom category из directory; viewer получает ясный read-only
contract. Committed row появляется в Active view без full reload.

## Server

- `POST /api/v1/categories`;
- explicit name/notes length and whitespace normalization;
- case-insensitive workspace uniqueness;
- allowed custom kind values and server-provided explanations;
- 201 committed summary, stable validation/field errors;
- session/write/CSRF/isolation tests.

## React

- `WorkbenchPanel` opened by the single page primary CTA;
- `Field`/`Fieldset`/form layout, visible labels and kind helper text;
- client usability validation plus server authority;
- first-invalid focus, pending lock, draft preservation and dirty-close dialog;
- authoritative collection insert, URL reset if needed, Toast and trigger focus
  return;
- reuse Import Review category create semantics, not its embedded UI layout.

## Exit gate

- duplicate/blank/oversized/network/401/403 paths covered;
- new row is searchable and links to detail;
- no generic form abstraction and no direct SSR POST from React.

