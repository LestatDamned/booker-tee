# PROJECT_VISION.md — Booker Tee

Product vision and positioning for Booker Tee.

This document is the product-level source of truth. Coding agents should read it before making major UX, domain, reporting, onboarding, import, or analytics decisions. `AGENTS.md` defines engineering rules. `DOMAIN_MODEL.md` defines the data model. This file defines why the product exists and who it is for.

---

## 1. One-sentence vision

**Booker Tee helps financially aware people turn scattered money movements into a clear, reliable picture of cash flow, profit, assets, and financial results.**

Booker Tee is not traditional accounting software. It is a private financial analysis and management tool for people who need to understand money flows across personal life, family, property, and small business activities.

---

## 2. Product thesis

Many people already care about their finances, but their real financial life is fragmented:

- cash in pockets, safes, and envelopes;
- personal cards and business cards;
- bank accounts and deposits;
- rent payments from tenants;
- repairs, utilities, taxes, contractor payments;
- family expenses mixed with business expenses;
- PDF bank statements, receipts, documents, and manual notes.

They do not necessarily need formal bookkeeping, statutory accounting, payroll, ERP, or tax reporting.

They need a simple and reliable system that answers practical questions:

- Where did the money come from?
- Where did the money go?
- Where is the money now?
- Which activity, property, project, or workspace produced the result?
- Which transactions are confirmed, suspicious, duplicated, or still waiting for review?
- What is the real cash flow, not just the bank balance?

The core product promise:

```text
Import / enter money movements
  -> preserve raw source data
  -> normalize transactions
  -> validate and deduplicate
  -> let the user review
  -> produce clear reports and metrics
```

---

## 3. Target audience

Booker Tee is built for financially aware users who already want control and clarity.

### 3.1 Financially aware individuals

People who track or want to track their personal finances, accounts, cards, cash, deposits, categories, and recurring payments.

They are not satisfied with vague bank app analytics because they need a more flexible view across multiple accounts and sources.

### 3.2 Family finance managers

People who want to understand shared household spending, family cash flow, common goals, recurring obligations, and shared accounts.

They need collaboration, but not corporate accounting complexity.

### 3.3 DIY landlords

People who own and manage rental properties themselves.

They need each property to act as a financial center:

- rent income;
- repairs;
- utilities;
- tenant deposits;
- taxes;
- insurance;
- maintenance;
- vacancy impact in later versions.

They need to know the real result of each property, not just see incoming rent.

### 3.4 Small entrepreneurs

People running small entrepreneurial activity where money flows through cards, cash, bank accounts, deposits, contractors, customers, and informal operational notes.

They need management finance: cash position, income, expense, profit, obligations, and trends.

They do not want a heavy accounting system built for accountants.

### 3.5 Small businesses and microbusinesses

Small teams and owner-operated businesses that need a simple financial command center.

They need reports, transaction review, controlled imports, roles, workspace separation, and visibility into where money goes.

### 3.6 Trusted collaborators

Later versions should support spouses, family members, assistants, property managers, and analysts.

These users may upload documents, classify expenses, review reports, or manage a specific workspace, but they should not automatically see every balance, deposit, profit metric, or private account.

---

## 4. User mindset

Booker Tee users are not casual budget app users who only want colorful charts.

They are more serious:

- they already understand that money must be tracked;
- they are willing to review unclear transactions;
- they care about correctness;
- they want reliable reports;
- they may have multiple financial contexts;
- they may mix cash, cards, bank transfers, deposits, and property income;
- they want automation, but not at the cost of wrong numbers.

The product should feel like a trustworthy financial cockpit, not a toy.

---

## 5. What Booker Tee is

Booker Tee is:

- a private financial management assistant;
- a reliable bank statement importer;
- a review-first transaction system;
- a cash-flow and profit analysis tool;
- a workspace-based money management system;
- a property-aware financial tracker;
- a future document and financial memory layer;
- a simple management reporting tool for people who are not accountants.

Booker Tee should help the user move from messy financial fragments to structured financial understanding.

---

## 6. What Booker Tee is not

Booker Tee is not:

- full statutory accounting software;
- a tax filing product;
- payroll software;
- ERP;
- CRM;
- inventory management;
- a trading terminal;
- a bank replacement;
- a personal finance game;
- an AI chatbot with finance features attached;
- a product that silently guesses and mutates financial records without review.

Booker Tee may later integrate with accountants, exports, AI search, and advanced analytics, but the first product must remain focused on reliable financial data and clear reporting.

---

## 7. Core product principle

### Simple enough for non-accountants. Precise enough for people who care.

The user should not need to understand double-entry bookkeeping terminology to use Booker Tee.

But the system itself must preserve financial correctness:

- internal transfers must not become income;
- deposits from cash to card must not double-count money;
- tenant security deposits must not count as profit until retained;
- failed imports must not pollute reports;
- duplicate statements must not double-count transactions;
- reports must be based on confirmed or explicitly accepted data.

---

## 8. Primary product promise

Booker Tee should answer four questions better than a bank app or spreadsheet:

### 8.1 Where did money come from?

Examples:

- rent from property `9 Maya 20`;
- customer payment;
- salary;
- refund;
- owner contribution;
- retained tenant deposit;
- sale of an asset.

### 8.2 Where did money go?

Examples:

- repair;
- groceries;
- utilities;
- contractor;
- tax;
- family expense;
- property maintenance;
- business purchase.

### 8.3 Where is money now?

Examples:

- cash safe;
- wallet;
- personal card;
- business card;
- checking account;
- deposit;
- virtual envelope in a later version.

### 8.4 What result did it produce?

Examples:

- property profit;
- family spending by category;
- business cash flow;
- monthly net result;
- account balance by source;
- unreviewed imported transactions;
- suspicious mismatches.

---

## 9. Workspace vision

Booker Tee should be workspace-first.

A workspace is a strict financial context and data boundary.

Examples:

```text
Personal
Family
Rental Properties
Small Business
Project
```

The same user may manage several workspaces. Each workspace has its own accounts, categories, properties, transaction rules, documents, reports, and members.

Workspace separation prevents the common mistake of mixing personal, family, business, and property finances into one confusing stream.

The MVP may create only one default personal workspace, but the architecture must support multiple workspaces from the beginning.

---

## 10. Accounting philosophy without accounting complexity

Booker Tee should avoid presenting itself as traditional bookkeeping, but it must still use sound financial logic internally.

User-facing language should prefer:

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

Avoid making the core UI feel like accounting software with terms such as:

```text
Chart of accounts
Debit
Credit
Ledger
Trial balance
Journal posting
```

The domain model may use accounting-inspired structure internally, especially `Operation -> MoneyEntry`, but the interface should remain practical and easy to understand.

---

## 11. Critical financial rule: transfers are not income

Booker Tee must never confuse internal money movement with real financial result.

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

Only the first event changes profit. The second and third events only change where the same money is stored.

This rule is central to product trust.

---

## 12. PDF import is the first wedge

The first strong product wedge is reliable import of bank statements, especially PDF statements.

Why this matters:

- users already have bank statements;
- many banks do not provide convenient APIs for personal users;
- manual entry is too slow;
- bank apps do not understand the user's full context;
- reliable import creates the data foundation for all reports.

The import pipeline should be:

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

Imported data must be reviewable. Raw source data must be preserved. Failed parsing must not delete files. Control-total mismatches must require review.

---

## 13. Reporting vision

Reports should be simple, useful, and explainable.

Core report types:

### 13.1 Cash position

Shows where money is now:

- by account;
- by account type;
- by workspace;
- by currency in later versions.

### 13.2 Cash flow

Shows money movement over time:

- income;
- expenses;
- internal transfers separately;
- net result;
- opening and closing balance where possible.

### 13.3 Category report

Shows what money was spent on or received for:

- groceries;
- repairs;
- utilities;
- rent income;
- contractor payments;
- taxes;
- family expenses;
- business expenses.

### 13.4 Property result

Shows the financial result of each rental property:

- rent income;
- repair expenses;
- utility expenses;
- taxes;
- insurance;
- retained deposits;
- net operating result;
- ROI and vacancy metrics in later versions.

### 13.5 Review and data quality report

Shows trust level of the data:

- unreviewed transactions;
- failed parse attempts;
- duplicate candidates;
- control-total mismatches;
- imported rows not linked to confirmed operations;
- rules that need confirmation.

A financial report is only useful if the user can trust the underlying data.

---

## 14. Property management vision

Property support should start simple and become deeper over time.

MVP-level property support:

- create a property;
- link income and expenses to a property;
- view property income, expenses, and net result.

Later property features:

- tenant profiles;
- lease terms;
- security deposits;
- meter readings;
- recurring rent expectations;
- vacancy tracking;
- document storage;
- repair history;
- profitability comparison across properties.

Property support should remain financial-first. Booker Tee is not initially a full property management CRM.

---

## 15. Collaboration vision

Collaboration should be based on workspace membership and roles.

Future users may include:

- spouse;
- family member;
- business partner;
- assistant;
- property manager;
- analyst;
- accountant or bookkeeper.

Access must be intentional and scoped:

- a spouse may manage family expenses;
- an assistant may upload PDF statements without seeing sensitive balances;
- a property manager may manage property documents and expenses;
- an analyst may view reports without editing transactions.

Do not build full collaboration before the core import and review workflow is stable, but keep the architecture ready.

---

## 16. Automation philosophy

Automation should reduce repetitive work, not hide uncertainty.

Good automation:

- suggest a category based on past confirmed behavior;
- suggest a property based on payer, description, amount, and pattern;
- detect possible internal transfers;
- detect duplicate imported rows;
- detect recurring rent payments;
- detect statement control-total mismatches;
- ask for review when confidence is low.

Bad automation:

- silently marks unclear income as confirmed;
- guesses property links without review;
- counts transfers as profit;
- deletes raw imported data;
- hides parser errors;
- changes reports without explaining why.

Booker Tee should be conservative by default.

---

## 17. AI vision

AI is a future amplifier, not the MVP foundation.

AI may later help with:

- semantic search across documents and transactions;
- natural-language report queries;
- matching messy bank descriptions to known categories;
- finding suspicious movements;
- summarizing financial periods;
- explaining cash-flow changes.

But the first version should not depend on AI to produce correct financial results.

The correct foundation is structured data, deterministic validation, review flow, and clear reports.

---

## 18. Privacy vision

Booker Tee handles sensitive financial information.

Product decisions must respect privacy:

- do not send private financial data to external AI or analytics APIs unless the user explicitly opts in;
- preserve strict workspace boundaries;
- design future roles around least privilege;
- make exports and data deletion explicit;
- store raw documents securely;
- avoid accidental data leaks in logs, errors, and debug views.

Trust is a product feature.

---

## 19. UX personality

Booker Tee should feel:

- clear;
- strict;
- reliable;
- private;
- analytical;
- calm;
- practical;
- built for people who care about numbers.

It should not feel:

- childish;
- gamified;
- noisy;
- over-automated;
- corporate and bureaucratic;
- like a tax-accounting suite;
- like a generic AI wrapper.

The interface should prioritize review, tables, filters, reports, status indicators, and traceability.

---

## 20. MVP scope

The MVP should prove that Booker Tee can reliably transform messy financial inputs into useful reports.

MVP must focus on:

- default workspace;
- accounts/wallets;
- manual income, expense, transfer, and adjustment operations;
- PDF document upload;
- parse attempts;
- raw transaction preservation;
- normalized draft records;
- review queue;
- confirmation flow;
- categories;
- basic transaction rules;
- basic property linking;
- basic reports;
- duplicate prevention;
- control-total validation where available.

MVP should not focus on:

- full AI/RAG;
- Text-to-SQL;
- full document knowledge base;
- advanced RBAC UI;
- Telegram bot;
- IMAP ingestion;
- full property CRM;
- tax filing;
- payroll;
- invoices;
- ERP workflows;
- complex dashboards before data quality is solved.

---

## 21. North Star

The North Star is not the number of imported files, charts, or AI responses.

The North Star is:

```text
The user trusts Booker Tee as the place where their real financial picture becomes clear.
```

A user should eventually be able to say:

```text
I know where my money came from.
I know where it went.
I know where it is now.
I know which activity produced profit or loss.
I trust the numbers because the system preserves sources, validates imports, and asks me to review uncertainty.
```

---

## 22. Product positioning

Recommended positioning:

> Booker Tee is a private financial management tool for financially aware individuals, DIY landlords, small entrepreneurs, and small businesses. It turns bank statements, cash movements, and manual records into clean transactions, reliable reports, and clear financial metrics without forcing users into heavy accounting software.

Shorter positioning:

> Booker Tee helps you understand money flows across personal life, family, property, and small business — simply, privately, and reliably.

MVP positioning:

> Booker Tee turns PDF bank statements and manual money movements into reviewed transactions, account balances, categories, property-linked results, and simple financial reports.

---

## 23. Decision filter for new features

Before adding a feature, ask:

1. Does it improve financial clarity?
2. Does it improve data reliability?
3. Does it reduce manual review without hiding uncertainty?
4. Does it respect workspace boundaries?
5. Does it avoid counting the same money twice?
6. Does it help the target audience understand cash flow, profit, assets, or property results?
7. Is it necessary for the current phase, or should it wait until after the import/review core is stable?

If a feature does not help the user understand financial flows or trust the reports, it should not be part of the MVP.

---

## 24. Product mantra

```text
Reliable financial clarity, not heavy accounting.
```

Booker Tee should help serious users understand their money without forcing them to become accountants.
