# Booker Tee roadmap

Статус: направления продукта, не sprint backlog.

## Сейчас

1. Сохранять надёжность import/review/ledger:
   - raw source и parse attempts не теряются;
   - retry и повторный импорт не удваивают деньги;
   - большие payloads и review queues остаются ограниченными;
   - новые parsers используют только sanitized fixtures.
2. Подготовить и проверить production release:
   - backup/restore;
   - production preflight и image audit;
   - TLS, secrets, invite-only registration и Telegram webhook;
   - ограниченный smoke с вымышленными данными.
3. Улучшать correction/audit UX подтверждённых операций по реальному
   использованию, не ослабляя source-specific invariants.

## Следом

- решить, нужен ли routing cutover без временного `/app` prefix;
- измерить производительность больших imports и reports;
- улучшить account/report flows по наблюдаемым сценариям;
- подтвердить production email delivery и двухпользовательский collaboration
  flow.

## Только при подтверждённой потребности

- новые bank parsers и более точные transaction rules;
- debt schedules и reminders;
- дополнительные property analytics;
- узкие chat workflows поверх существующих use cases.

Не планируются без отдельного product decision: внешняя AI-обработка финансовых
данных, ERP/CRM/tax suite, microfrontends, permissive cross-origin API,
background infrastructure без измеренной причины и cross-workspace accounting.

Постоянные ограничения находятся в
[`DOMAIN_MODEL.md`](../domain/DOMAIN_MODEL.md); конкретная задача должна жить в
issue/task, а не превращать roadmap в журнал реализации.
