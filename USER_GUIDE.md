# USER_GUIDE.md — Booker Tee

Product guidance plan for teaching users how to use Booker Tee without turning the app into a tutorial-heavy product.

This document defines what the UI should teach, where it should teach it, and in what order to implement guidance. It complements:

- `PROJECT_VISION.md` — why the product exists;
- `MVP.md` — parser-first MVP scope;
- `DOMAIN_MODEL.md` — financial concepts and invariants;
- `AGENTS.md` — engineering and product constraints.

## 1. Guidance goal

Booker Tee should teach users through the workflow itself:

```text
You are here.
This is already done.
This needs attention.
This is the safest next action.
```

Do not make the first MVP depend on a separate manual, long onboarding tour, AI assistant, or help center. The best user guide is a sequence of precise next-step prompts inside the actual financial import flow.

## 2. Product teaching principles

1. Teach the workflow, not every button.
2. Keep guidance close to the action it explains.
3. Explain only business-critical concepts inline.
4. Prefer one recommended next action over many choices.
5. Never hide financial consequences behind vague labels.
6. Do not add noisy instructional text inside every transaction card.
7. Preserve expert speed: guidance must not slow down repeated review work.

## 3. Concepts the user must learn

### Workspace

User must understand that a workspace is the financial boundary. Accounts, categories, documents, and reports belong to the selected workspace.

Teach on:

- `/workspaces`
- dashboard header/context strip
- empty states for accounts/imports/reports

Avoid long explanations after the user already has an active workspace.

### Account

User must understand that every statement is imported into one account, because ledger entries and balances depend on it.

Teach on:

- `/accounts`
- `/imports/upload`
- account empty state on dashboard

Key message:

```text
Create the account where this money lives before importing a statement.
```

### Import Pipeline

User must understand the pipeline:

```text
Upload -> Extract -> Map if needed -> Review -> Confirm -> Reports
```

Teach on:

- `/imports`
- `/imports/upload`
- `/imports/documents/{id}`
- `/imports/documents/{id}/mapping`
- `/imports/documents/{id}/review`

This should be a compact step indicator, not a marketing hero.

### Review Statuses

User must understand:

- `normalized` means ready but not confirmed;
- `suggested` means a rule proposed classification;
- `needs_review` means the system is uncertain;
- `possible_duplicate` requires a decision;
- `confirmed` means posted to ledger;
- `ignored` and `duplicate` do not affect reports.

Teach on:

- review header summary;
- row badges through short labels;
- row-level flags only when there is a real issue.

### Income, Expense, Transfer

User must understand the critical financial rule:

```text
Income/expense affects profit. Transfer only moves money between accounts.
```

Teach on:

- transfer accordion in review;
- manual operations page;
- reports if transfer rows are excluded.

Do not bury this in documentation. It must appear where a user can accidentally classify a transfer as income or expense.

### Categories and Rules

User must understand:

- categories explain why money moved;
- rules suggest future categories;
- rules should help review, not silently mutate financial truth.

Teach on:

- category selector in review;
- `Create rule` checkbox;
- `/rules` page.

Key message near `Create rule`:

```text
Use this when similar descriptions should get the same category next time.
```

Also teach on:

- `/categories`
- `/rules`

Recommended guidance:

- categories page explains that categories drive reports;
- rules page explains that rules prefill/suggest review decisions, but do not replace review;
- empty rule/category states should point to the creation form.

### Manual Operations

User must understand when to create an operation manually instead of importing it from a statement.

Teach on:

- `/ledger/manual`

Key message:

```text
Use manual operations for cash movements, corrections, and one-off entries outside imported statements.
Income/expense affects profit. Transfer only moves money between accounts.
```

Recommended guidance:

- short local hint above the manual operation form;
- empty state explains why an account is required;
- empty list explains when manual operations are useful.

### Raw Data Preservation

User should trust that raw imported rows are preserved even if normalization or review changes.

Teach lightly on:

- document detail page;
- parse attempt history.

Do not over-explain internals on the main review screen.

## 4. Guidance components

### 4.1 Next Step Panel

A compact panel at the top of workflow pages. It answers:

- current stage;
- what is blocking progress;
- one recommended action.

Example:

```text
Next: Review extracted rows
27 rows were extracted. Confirm income/expense rows, mark transfers, and ignore duplicates.
[Open review]
```

Use on:

- dashboard;
- imports index;
- upload page;
- document detail;
- mapping page;
- review page.

Rules:

- one primary button;
- optional secondary link only when necessary;
- no long paragraphs.

### 4.2 Import Step Indicator

Compact status strip for one document:

```text
Upload -> Extract -> Mapping -> Review -> Ledger
```

State examples:

- done;
- current;
- blocked;
- skipped.

Use on:

- document detail;
- mapping;
- review.

Rules:

- visual status must come from document/validation state;
- do not let the user think confirmed ledger exists before review is done.

### 4.3 Empty States

Empty states should teach the next prerequisite.

Examples:

```text
No accounts yet.
Create an account before uploading a statement, so imported rows have a balance destination.
```

```text
No raw rows yet.
Reparse the document or configure columns before review.
```

Use on:

- dashboard cards;
- accounts index;
- imports index;
- upload page;
- document detail;
- review page.

### 4.4 Inline Critical Hints

Short, local hints for dangerous or non-obvious financial actions.

Use for:

- transfer does not affect profit;
- possible duplicate;
- create rule;
- failed validation totals;
- mapping unknown columns.

Avoid generic hints like:

```text
Click this button to continue.
```

### 4.5 Completion State

When all reviewable rows are handled, show a clear completion state:

```text
Import reviewed
All rows are confirmed, ignored, or marked as duplicates.
[Open report] [Back to imports]
```

Use on:

- review page.

## 5. Workflow-specific guidance

### Home / Dashboard

Current problem:

The home page shows actions, but the user loses the sequence after clicking into a specific page.

Target behavior:

- show a persistent onboarding checklist until the workspace has basic setup;
- show active work items after setup;
- highlight documents requiring review.

Checklist:

```text
1. Create workspace
2. Add accounts
3. Upload statement
4. Review rows
5. Open reports
```

The checklist should mark completed items from real data, not from local browser state.

### Accounts

Teach:

- account is where money is stored;
- statement import needs an account;
- internal transfers require at least two accounts to model movement correctly.

Recommended guidance:

- empty state with `Create account`;
- short hint near account type/currency fields.

### Upload

Teach:

- upload is tied to a selected account;
- raw file is preserved;
- accepted formats are PDF/XLSX.

Recommended guidance:

- next step panel above upload form;
- if no accounts exist, explain why account creation comes first.

### Document Detail

Teach:

- what happened to the uploaded document;
- whether extraction succeeded;
- whether mapping is needed;
- what next action to take.

Recommended guidance:

- import step indicator;
- next step panel;
- keep raw/technical data lower on the page.

### Mapping

Teach:

- mapping is needed only when the parser cannot confidently recognize columns;
- user is turning table columns into reviewable raw transactions;
- preview is not confirmed accounting.

Recommended guidance:

- step indicator;
- local hints for required columns;
- preview warnings near preview table.

### Review

Teach:

- review is where raw rows become ledger operations;
- confirmed rows affect reports;
- ignored/duplicates do not;
- transfers do not affect profit;
- rules only suggest future classification.

Recommended guidance:

- compact next step panel with remaining counts;
- completion state when no rows require action;
- inline hint for transfer accordion;
- inline hint for `Create rule`;
- keep transaction cards dense.

### Reports

Teach:

- reports are based on confirmed ledger entries;
- ignored/duplicate rows are excluded;
- transfers are excluded from profit.

Recommended guidance:

- empty state if no confirmed operations exist;
- small note near profit summary.

## 6. Implementation phases

### Phase 1 — Documented UX Contract

Goal:

Write this guide and align future UI tasks around it.

Deliverables:

- `USER_GUIDE.md`
- no runtime behavior change required.

Status:

```text
done
```

### Phase 2 — Next Step Panel Foundation

Goal:

Add a reusable server-rendered component for workflow guidance.

Deliverables:

- `templates/components/next_step.html`
- lightweight DTO/helper for title, message, primary action;
- first usage on dashboard/imports pages.

Initial implementation:

- `templates/components/next_step.html`
- dashboard summary
- imports index
- upload page
- document detail
- mapping page
- review page

Acceptance:

- no page has more than one primary next action;
- no component contains hardcoded fake progress.

Status:

```text
done
```

### Phase 3 — Import Step Indicator

Goal:

Show where a document is in the import pipeline.

Deliverables:

- `templates/imports/_workflow_steps.html`
- helper that maps document status and validation state to steps.

Initial implementation:

- `templates/imports/_workflow_steps.html`
- document detail
- mapping page
- review page

Acceptance:

- document detail, mapping, and review show the same step state;
- mapping-required documents clearly point to mapping;
- review-ready documents clearly point to review.

Status:

```text
done
```

### Phase 4 — Better Empty States

Goal:

Make empty states teach prerequisites.

Deliverables:

- dashboard account/import empty states;
- upload no-account state;
- review no-raw-rows state;
- reports no-confirmed-data state.

Initial implementation:

- reusable `templates/components/empty_state.html`
- accounts empty state points to the first-account form
- reports empty state distinguishes no accounts from no confirmed report data
- dashboard account/import empty states
- imports index empty state
- upload no-account empty state
- review no-raw-rows empty state

Acceptance:

- each empty state has one primary action;
- each explanation is one or two short sentences.

Status:

```text
done
```

### Phase 5 — Review Guidance

Goal:

Help users safely confirm rows without clutter.

Deliverables:

- review remaining-count panel;
- completion state;
- transfer hint;
- create-rule hint;
- possible duplicate hint.

Initial implementation:

- review remaining-count panel
- completion state
- reusable `templates/components/inline_hint.html`
- transfer hint inside transfer accordion
- create-rule hint near the checkbox
- possible duplicate hint on possible duplicate rows
- validation mismatch hint near the review validation summary

Acceptance:

- transaction cards remain fast to scan;
- no repeated wall of instructional text per row.

Status:

```text
done
```

### Phase 6 — Onboarding Checklist

Goal:

Persist the high-level setup sequence across screens until useful setup is complete.

Deliverables:

- dashboard checklist based on real workspace data;
- optional compact header/sidebar variant later.

Initial implementation:

- real `/dashboard` page
- dashboard navigation link
- workspace selection redirects to `/dashboard`
- reusable `templates/components/onboarding_checklist.html`
- checklist state derived from accounts, imported documents, review queue, and report data
- compact header/sidebar variant deferred until the final UX/UI audit shows it is needed

Acceptance:

- checklist items reflect actual database state;
- checklist does not appear as a blocking wizard.

Status:

```text
done
```

### Phase 7 — Supporting Feature Guidance

Goal:

Teach users how supporting sections help the import/review workflow.

Deliverables:

- category guidance on `/categories`;
- rule guidance on `/rules`;
- manual operation guidance on `/ledger/manual`.

Initial implementation:

- categories explain report impact and empty state points to the category form;
- rules explain suggestions/prefill behavior and empty state points to the rule form;
- manual operations explain cash/corrections/one-off entries and the income/expense/transfer distinction.

Acceptance:

- supporting pages explain why the feature exists;
- guidance stays close to the creation form;
- no page becomes a long manual.

Status:

```text
done
```

## 7. Non-goals for now

Do not build these for the MVP guidance layer:

- long documentation center;
- interactive overlay tour;
- AI chatbot guide;
- video walkthroughs;
- gamified onboarding;
- broad settings wizard;
- user-specific dismissed-tip persistence unless the UI becomes noisy.

## 8. Copy style

Use short, direct Russian UI copy.

Good:

```text
Следующий шаг: проверить строки
27 строк готовы к проверке. Подтвердите операции, отметьте переводы и игнорируйте дубли.
```

Avoid:

```text
Для того чтобы воспользоваться всеми возможностями приложения, пожалуйста, перейдите...
```

Prefer verbs:

- create;
- upload;
- review;
- confirm;
- map;
- open report.

Prefer business wording over implementation wording:

- "строки выписки" instead of "raw transactions";
- "проверка" instead of "review pipeline";
- "проведено" instead of "linked operation" unless showing technical details.

## 9. UX/UI audit notes

Final guidance audit decisions:

1. Dashboard checklist is the primary guide until setup is complete. Do not show a competing next-step panel during setup.
2. Empty states should not repeat the same primary action already shown by a next-step panel on the same screen.
3. Reports should show one strong empty state when there is no report data, not separate "no data" notices for every report section.
4. Mapping next-step links should jump to the action area that matches the suggested action, not merely to the top of the form.
5. Supporting feature hints should stay short and local to the form; no separate help/manual page for MVP.

## 10. Open questions

1. Should users be able to hide guidance once they are comfortable?
2. Should review completion automatically suggest reports, imports index, or next document requiring review?
3. Should the compact checklist variant be added to the header/sidebar after more real usage?
