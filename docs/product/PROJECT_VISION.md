# PROJECT_VISION.md - Booker Tee

Product vision and positioning for Booker Tee.

Status: active product compass.

Read this document when changing product scope, UX direction, import/review
behavior, reporting, onboarding, workspace behavior, automation, or user-facing
language.

This file explains why Booker Tee exists. It is not a task checklist.

Use:

- [`ROADMAP.md`](./ROADMAP.md) for sequencing and planning.
- [`MVP.md`](./MVP.md) as historical MVP baseline and guardrails.
- [`DOMAIN_MODEL.md`](../domain/DOMAIN_MODEL.md) for financial/domain rules.
- [`ARCHITECTURE.md`](../architecture/ARCHITECTURE.md) for implementation shape.
- [`REACT_FRONTEND_DESIGN.md`](../design/REACT_FRONTEND_DESIGN.md) for the active
  React/API architecture and migration strategy.
- [`FRONTEND_NEXT_DESIGN.md`](../design/FRONTEND_NEXT_DESIGN.md) only for
  superseded SSR behavior discoveries.
- [`REFACTOR_PROJECT_DESIGN.md`](../design/REFACTOR_PROJECT_DESIGN.md) only for
  historical legacy frontend behavior and implementation discoveries.

Current assessment: the original MVP has been completed and exceeded. Booker Tee
already has workspaces, users, accounts, imports, review, operations, money
entries, categories, properties, rules, reports, manual operations, workspace
membership, and unknown statement mapping. The active challenge is to make the
product clearer, more reliable, easier to maintain, and ready for deeper
workflows without losing the review-first financial core.

---

## 1. Vision

**Booker Tee helps financially aware people turn scattered money movements into
a clear, reliable picture of cash flow, profit, assets, and financial results.**

Booker Tee is not traditional accounting software. It is a private financial
analysis and management tool for people who need to understand money flows
across personal life, family, property, and small business activity.

The product promise:

```text
Import or enter money movements
  -> preserve raw source data
  -> normalize transactions
  -> validate and deduplicate
  -> let the user review uncertainty
  -> produce clear reports and metrics
```

---

## 2. Product Thesis

Real financial life is fragmented:

- cash, cards, bank accounts, deposits, and wallets;
- family, property, personal, and small business expenses mixed together;
- rent, repairs, utilities, taxes, contractors, refunds, and manual notes;
- PDF bank statements and source documents that need preservation.

Many users do not need statutory accounting, payroll, ERP, or tax filing. They
need a reliable system that answers:

- Where did money come from?
- Where did it go?
- Where is it now?
- Which property, project, family context, or workspace produced the result?
- Which transactions are confirmed, suspicious, duplicated, or still waiting for
  review?

---

## 3. Target Users

Booker Tee is for financially aware users who already want control and clarity.

- Individuals who track accounts, cards, cash, deposits, categories, and
  recurring payments.
- Family finance managers who need shared visibility without corporate
  accounting complexity.
- DIY landlords who need income, expenses, deposits, repairs, and net result per
  property.
- Small entrepreneurs and microbusinesses that need management finance, not a
  heavy accounting suite.
- Trusted collaborators such as spouses, assistants, property managers,
  analysts, and accountants, with intentional scoped access.

---

## 4. What Booker Tee Is

Booker Tee is:

- a private financial management assistant;
- a reliable bank statement importer;
- a review-first transaction system;
- a cash-flow and profit analysis tool;
- a workspace-based money management system;
- a property-aware financial tracker;
- a simple reporting tool for people who care about numbers;
- a future financial memory layer built on trustworthy structured data.

Booker Tee is not:

- statutory accounting, tax filing, payroll, ERP, CRM, or inventory management;
- a trading terminal or bank replacement;
- a personal finance game;
- an AI chatbot with finance features attached;
- a system that silently guesses and mutates financial records without review.

---

## 5. Product Principles

Simple enough for non-accountants. Precise enough for people who care.

Non-negotiable rules:

- internal transfers must not become income or expense;
- moving cash to a card must not double-count money;
- tenant security deposits must not count as profit until retained;
- failed imports must not pollute reports;
- duplicate statements must not double-count transactions;
- raw imported data must be preserved;
- uncertain data must go through review;
- reports must be based on confirmed or explicitly accepted data;
- workspace boundaries must be strict;
- private financial data must not be sent to external AI/API services unless the
  user explicitly opts in.

---

## 6. Financial Questions

Booker Tee should answer four questions better than a bank app or spreadsheet.

Where did money come from?

- rent, salary, customer payment, refund, owner contribution, retained deposit,
  asset sale.

Where did money go?

- repairs, groceries, utilities, contractors, taxes, family expenses, property
  maintenance, business purchases.

Where is money now?

- cash safe, wallet, personal card, business card, checking account, deposit,
  future virtual envelope.

What result did it produce?

- property profit, family spending, business cash flow, monthly net result,
  account balances, unreviewed rows, suspicious mismatches.

---

## 7. Workspace Vision

Booker Tee is workspace-first.

A workspace is a strict financial context and data boundary:

```text
Personal
Family
Rental Properties
Small Business
Project
```

Each workspace owns its accounts, categories, properties, transaction rules,
documents, reports, operations, and members. Workspace separation prevents
personal, family, business, and property finances from becoming one confusing
stream.

---

## 8. Financial Language

The UI should avoid feeling like traditional bookkeeping software, but the system
must use sound financial logic internally.

Prefer:

```text
Account / Wallet
Money movement
Income
Expense
Transfer
Adjustment
Category
Property
Workspace
Report
Review
```

Avoid making the core UI depend on:

```text
Chart of accounts
Debit
Credit
Trial balance
Journal posting
```

The implementation may use accounting-inspired structure internally, especially
`Operation -> MoneyEntry`, while the interface stays practical and readable.

---

## 9. Critical Rule: Transfers Are Not Income

Booker Tee must never confuse internal money movement with real financial
result.

Example:

```text
1. Received 40,000 RUB cash rent for property "9 Maya 20"
2. Deposited this cash to a bank card
3. Moved money from the card to a deposit
```

Correct interpretation:

```text
1. Income: +40,000 RUB, property = 9 Maya 20, affects profit = true
2. Transfer: cash -> card, affects profit = false
3. Transfer: card -> deposit, affects profit = false
```

Only the first event changes profit. The second and third events only change
where the same money is stored.

---

## 10. Import And Review

Reliable bank statement import, especially PDF import, is the first strong
product wedge.

The pipeline should stay reviewable:

```text
Uploaded document
  -> parse attempt
  -> raw extracted rows
  -> normalized draft transactions
  -> validation
  -> deduplication
  -> review queue
  -> confirmed operations
```

Imported data must be explainable. Raw source data must be preserved. Failed
parsing must not delete files. Control-total mismatches and uncertain rows must
require review.

Current active UX focus: make review clear and consistent while migrating to
React. The API supplies server-owned financial semantics and capabilities;
components render them without deciding financial state, permissions,
suggestions or confirmation readiness.

---

## 11. Reporting Vision

Reports should be simple, useful, and explainable.

Core report types:

- cash position: where money is now;
- cash flow: income, expenses, transfers, and net result over time;
- category report: why money appeared or disappeared;
- property result: income, expenses, and net result per property;
- data quality report: unreviewed rows, failed imports, duplicate candidates,
  mismatches, and rows not linked to confirmed operations.

A financial report is only useful if the user can trust the underlying data.

---

## 12. Property Vision

Property support should remain financial-first.

Current and near-term property support:

- create a property;
- link income and expenses to a property;
- view property income, expenses, and net result.

Later property features may include tenants, lease terms, security deposits,
meters, recurring rent expectations, vacancy tracking, documents, repair
history, and profitability comparison. Booker Tee is not initially a full
property management CRM.

---

## 13. Collaboration Vision

Collaboration should be based on workspace membership and roles.

Access must be intentional and scoped:

- a spouse may manage family expenses;
- an assistant may upload statements without seeing sensitive balances;
- a property manager may manage property documents and expenses;
- an analyst may view reports without editing transactions.

Do not let collaboration features weaken workspace isolation or financial
privacy.

---

## 14. Automation And AI

Automation should reduce repetitive work, not hide uncertainty.

Good automation suggests categories/properties, detects transfers, finds
duplicates, notices recurring rent, checks control totals, and asks for review
when confidence is low.

Bad automation silently confirms unclear data, guesses property links without
review, counts transfers as profit, deletes raw source data, hides parser errors,
or changes reports without explaining why.

AI is a future amplifier, not the product foundation. It may later help with
semantic search, natural-language report queries, messy description matching,
suspicious movement detection, period summaries, and cash-flow explanations.

The reliable foundation is structured data, deterministic validation, review
flow, and clear reports.

---

## 15. Privacy Vision

Booker Tee handles sensitive financial information.

Product decisions must respect privacy:

- do not send private financial data to external AI or analytics APIs unless the
  user explicitly opts in;
- preserve strict workspace boundaries;
- design future roles around least privilege;
- make exports and data deletion explicit;
- store raw documents securely;
- avoid accidental data leaks in logs, errors, and debug views.

Trust is a product feature.

---

## 16. UX Personality

Booker Tee should feel clear, strict, reliable, private, analytical, calm,
practical, and built for people who care about numbers.

It should not feel childish, gamified, noisy, over-automated, corporate,
bureaucratic, like a tax-accounting suite, or like a generic AI wrapper.

The interface should prioritize review, tables, filters, reports, status
indicators, traceability, and predictable actions.

---

## 17. Current Product Baseline

The original MVP target has become the product baseline.

Booker Tee should preserve and refine:

- workspace/user/account foundations;
- document upload and parse attempts;
- raw transaction preservation;
- normalization, validation, and review;
- confirmed operations and money entries;
- manual income, expense, transfer, and adjustment operations;
- categories, properties, and transaction rules;
- duplicate prevention and reparse safety;
- account balances and financial reports;
- workspace membership and invitations;
- unknown statement mapping;
- clear, testable browser workflows across the React migration.

New work should improve clarity and reliability before widening the product.

---

## 18. Product Positioning

Recommended positioning:

> Booker Tee is a private financial management tool for financially aware
> individuals, DIY landlords, small entrepreneurs, and small businesses. It turns
> bank statements, cash movements, and manual records into clean transactions,
> reliable reports, and clear financial metrics without forcing users into heavy
> accounting software.

Shorter positioning:

> Booker Tee helps you understand money flows across personal life, family,
> property, and small business - simply, privately, and reliably.

---

## 19. Decision Filter

Before adding a feature, ask:

1. Does it improve financial clarity?
2. Does it improve data reliability?
3. Does it reduce manual review without hiding uncertainty?
4. Does it respect workspace boundaries?
5. Does it avoid counting the same money twice?
6. Does it help the target user understand cash flow, profit, assets, or
   property results?
7. Is it necessary for the current phase, or should it wait until the
   import/review core is clearer?

If a feature does not help the user understand financial flows or trust the
reports, it should wait.

---

## 20. North Star

The North Star is:

```text
The user trusts Booker Tee as the place where their real financial picture
becomes clear.
```

A user should eventually be able to say:

```text
I know where my money came from.
I know where it went.
I know where it is now.
I know which activity produced profit or loss.
I trust the numbers because the system preserves sources, validates imports,
and asks me to review uncertainty.
```

---

## 21. Product Mantra

```text
Reliable financial clarity, not heavy accounting.
```

Booker Tee should help serious users understand their money without forcing them
to become accountants.
