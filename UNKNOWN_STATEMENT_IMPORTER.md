# UNKNOWN_STATEMENT_IMPORTER.md - Universal unknown statement importer

This note records the direction for turning the current unknown statement fallback into
a genuinely reusable importer for statements that do not yet have a dedicated parser.

## Goal

The unknown statement importer should be a review-first table importer, not a silent
autonomous parser.

It should:

1. Preserve raw extracted text and tables.
2. Detect transaction-like tables by structure, not by one bank's phrases.
3. Suggest column mappings with confidence scores.
4. Let the user review and adjust mappings before import.
5. Save confirmed mappings as reusable templates.
6. Apply saved templates only when the table signature still matches.
7. Keep imported rows reviewable; never create confirmed ledger records directly.

## Non-goals

The unknown importer should not promise perfect parsing of every PDF. It should not
send financial data to external services. It should not auto-confirm accounting rows.

## Proposed pipeline

```text
ExtractedPdf
  -> statement profile
  -> transaction table detection
  -> column profiling
  -> mapping suggestions
  -> user preview and adjustment
  -> raw transactions
  -> validation and deduplication
  -> review
```

## Current text-only fallback

When `pdfplumber` extracts readable text but no usable transaction table, the
unknown importer now tries a conservative text fallback:

```text
text_by_page
  -> transaction-like lines
  -> synthetic table: Date / Description / Amount / Currency / Balance
  -> existing unknown mapping preview
  -> reviewable raw transactions
```

This fallback is intentionally review-first. It does not create confirmed ledger
records and it does not bypass the existing mapping screen. The synthetic table
is stored alongside the raw extracted tables for the parse attempt so the normal
unknown mapping flow can reuse column suggestions, previews, deduplication,
transaction rules, and statement-total validation.

The first implementation is heuristic and deliberately modest:

- a candidate line must contain a recognizable date and money amount;
- the first signed amount is treated as the operation amount when present;
- a later money value can be treated as balance after the operation;
- lines without a date or amount may be appended as description continuations;
- OCR, coordinate-based reconstruction, and bank-specific text layouts are not
  part of this fallback yet.

Known limitations:

- text extracted from PDFs may not preserve visual column order;
- unsigned amounts can be ambiguous when both operation amount and balance are
  present;
- multi-line transactions work only for simple continuation text;
- scanned PDFs still require OCR before this fallback can help.

Keep future improvements small and test-driven. Prefer adding sanitized text
fixtures for one failure mode at a time over making the extractor more magical.

## Statement profile

The profile should describe the document without relying on a dedicated parser:

- possible bank name from optional hints;
- possible statement type from optional hints;
- text-based vs scanned;
- page count and table count;
- currencies observed in text and tables;
- possible statement period;
- possible control totals.

Bank-specific hints belong in hint/config modules, not in the generic analyzer.

## Hint config

Unknown statement hints live in:

```text
src/app/features/imports/application/unknown_statement_hints.json
```

The config is intentionally small and non-magical. It helps the generic importer
recognize a likely bank name, statement type, and control-total labels. It must
not define transaction column mappings; column mapping remains structural and
review-first.

### Top-level shape

```json
{
  "generic_control_total_labels": {
    "opening_balance": ["Opening balance"],
    "closing_balance": ["Closing balance"],
    "total_inflow": ["Total credits"],
    "total_outflow": ["Total debits"]
  },
  "banks": []
}
```

`generic_control_total_labels` are labels that can appear in statements from many
banks. Bank-specific labels belong inside a bank entry.

### Adding a bank

Add a new object to `banks`:

```json
{
  "bank_name": "Example Bank",
  "markers": ["example bank", "пример банк"]
}
```

`markers` are lower-risk text fragments that identify the bank in extracted PDF
text. Keep them short and stable: bank name, legal name fragment, app/product
name. Do not use account numbers, card numbers, customer names, addresses, or
other private values.

Matching is case-insensitive after whitespace normalization, so `"Example Bank"`
and `"example   bank"` are treated similarly. The marker itself should still be
written in the natural spelling that appears in statements.

### Adding statement types

Use `statement_types` when the same bank has different statement layouts:

```json
{
  "bank_name": "Example Bank",
  "markers": ["example bank"],
  "statement_types": [
    {
      "statement_type": "card_statement",
      "markers": ["card statement"]
    },
    {
      "statement_type": "account_movement_statement",
      "markers": ["account movement"]
    }
  ]
}
```

All markers inside one `statement_types` entry must be present in the extracted
text for that statement type to match. Use stable document phrases, not row-level
transaction descriptions.

Statement type names should be stable snake_case strings. Prefer existing names
when possible:

- `card_statement`;
- `account_movement_statement`;
- `deposit_statement`.

### Adding control-total labels

Use `control_total_labels` when a bank has known labels for statement totals:

```json
{
  "bank_name": "Example Bank",
  "markers": ["example bank"],
  "control_total_labels": [
    {
      "opening_balance": ["Opening balance"],
      "closing_balance": ["Closing balance"],
      "total_inflow": ["Total credits"],
      "total_outflow": ["Total debits"]
    }
  ]
}
```

Each field is optional. Add only labels that are actually printed in statements.
The importer uses these labels to extract control totals and validate the mapped
rows, but a missing label should not prevent manual import.

Field meanings:

- `opening_balance`: balance at the beginning of the statement period;
- `closing_balance`: balance at the end of the statement period;
- `total_inflow`: total incoming amount for the statement period;
- `total_outflow`: total outgoing amount for the statement period.

### Checklist for changes

When editing `unknown_statement_hints.json`:

1. Use sanitized, non-private markers only.
2. Keep markers specific enough to avoid false bank detection.
3. Do not add column indexes or account-specific assumptions.
4. Add or update tests when behavior changes.
5. Run at least:

```bash
uv run pytest tests/test_unknown_statement_analysis.py -q
uv run ruff check src/app/features/imports/application/unknown_statements/hints.py tests/test_unknown_statement_analysis.py
```

## Sanitized fixtures

Unknown-statement fixtures should be sanitized extracted data, not original PDFs.
They live in:

```text
tests/fixtures/unknown_statements/
```

The fixture shape mirrors `ExtractedPdf`:

```json
{
  "text_by_page": ["...sanitized extracted text..."],
  "tables_by_page": [
    {
      "page_number": 1,
      "tables": [
        [
          ["Date", "Description", "Amount"],
          ["2026-05-12", "Coffee shop", "-5.50"]
        ]
      ]
    }
  ],
  "metadata": {
    "fixture_kind": "sanitized_unknown_statement",
    "source": "manual_sanitized_extracted_pdf_shape"
  }
}
```

Rules:

1. Do not commit real PDF files for unknown-statement fixtures.
2. Replace names, account numbers, card numbers, addresses, document IDs, and
   private descriptions with generic values.
3. Keep the structural behavior that matters: headers, column order, split
   debit/credit columns, continuation pages, posting dates, balances, and
   control-total labels.
4. Prefer small fixtures with 2-5 rows unless a larger shape is needed to
   reproduce a parser issue.
5. Add a test that uses the fixture through `analyze_unknown_statement()` and,
   when relevant, through mapping preview/import draft creation.

## Transaction table detection

Detection should be based on structural evidence:

- repeated date-like values;
- repeated money-like values;
- at least one text-like description/counterparty column;
- stable column count across rows;
- headers that mention dates, amounts, debits, credits, balances, currencies, or
  descriptions;
- continuation tables across pages.

Russian Ozon-style labels can contribute evidence, but must not be required.

## Column profiling

Each column should be profiled independently:

- `operation_date`;
- `posting_date`;
- `description`;
- `amount`;
- `debit_amount`;
- `credit_amount`;
- `currency`;
- `balance_after`;
- `reference`.

The current implementation supports a single signed `amount` column. A later step
should extend mapping commands to support `debit_amount` + `credit_amount`.

## Mapping suggestions

The importer should produce one or more suggested mappings. Each suggestion should
include:

- selected columns;
- first data row;
- default currency;
- confidence score;
- warnings, such as "split debit/credit table requires review".

The UI should keep the user in control: suggestions prefill the form, but the user
can override them.

## Template learning

When the user confirms a mapping, Booker Tee should store an import mapping template
with a table signature. Later uploads can reuse the template only when the signature
matches closely enough.

Auto-applied templates should still produce reviewable raw transactions, not
confirmed ledger entries.

## Implementation plan

1. Replace Ozon-shaped table detection with structural scoring.
2. Broaden header and sample-row column inference.
3. Add tests for non-Ozon table layouts.
4. Add column profiles and richer mapping suggestions.
5. Add split debit/credit mapping support.
6. Move bank-specific labels into hint/config modules.
7. Expand control-total extraction through generic labels plus bank hints.
8. Preserve and validate optional balance-after columns.
9. Surface row-level validation problems in the review UI.
10. Add posting-date mapping support.
11. Make saved template matching more tolerant through table/profile signatures.
12. Improve continuation-table detection across pages.
13. Add pre-import mapping consistency warnings.
14. Add more sanitized unknown-statement fixtures.

## Current progress

Done:

- Structural table detection no longer requires Ozon/RUB-specific rows.
- Header inference distinguishes signed amount, debit amount, credit amount, and
  currency candidates, plus optional balance-after columns.
- Manual mapping can import split debit/credit tables into signed raw
  transactions.
- Bank markers, statement type markers, and control-total labels live in a
  separate hint module.
- Generic English control-total labels are supported alongside bank hints.
- Table previews include column profiles with evidence counts for date-like,
  money-like, currency-like, description-like values and header matches.
- Table previews include mapping suggestions with selected columns, confidence,
  reasons, warnings, and first data row.
- Mapping suggestion reasons are structured evidence payloads rather than
  backend-owned UI strings.
- Mapping suggestion warnings are structured code payloads rather than
  backend-owned UI strings.
- The default mapping form uses the first compatible mapping suggestion before
  falling back to flat column candidates.
- Mapping suggestion confidence, reasons, and warnings are visible in the
  document detail and mapping screens, with localized reason rendering.
  Warnings are localized in the same UI component.
- Synthetic unknown-statement fixtures cover no-header tables and complete
  split debit/credit tables, including confidence and warning behavior.
- Unknown statement mapping can preserve an optional balance-after column in
  raw transactions.
- Unknown statement mapping can detect and preserve an optional posting-date
  column separately from the operation date.
- Saved mapping templates store mapped column profiles and can tolerate renamed
  headers when selected columns still look like dates, descriptions, amounts,
  currencies, and balances.
- Compatible table grouping can import headerless continuation tables on later
  pages even when PDF extraction gives them a different table index.
- Mapping preview surfaces pre-import consistency warnings for risky mappings:
  duplicate column roles, mixed signed/split amount choices, partial
  debit/credit mappings, high error rates, missing valid rows, and
  balance-after parse errors.
- Bank markers, statement type markers, and control-total labels are loaded
  from a small JSON hint config instead of Python constants.
- Sanitized extracted unknown-statement fixtures cover posting-date/balance
  layouts and split debit/credit continuation tables without committing real
  uploaded PDFs.
- Validation checks balance-after chains when consecutive mapped rows include
  both amounts and balances. It supports both oldest-first and newest-first
  statement order and reports mismatches for review.
- Balance-chain mismatches are surfaced next to affected rows in the review UI.

Next:

- Keep adding sanitized unknown-statement fixtures when safe samples reveal new
  layouts or parser edge cases.
