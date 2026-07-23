# Booker Tee Roadmap

Статус: planning reference, не sprint backlog.

Текущие исполняемые шаги находятся в
[`frontend/plan/README.md`](../frontend/plan/README.md). Этот файл задаёт порядок
продуктовых направлений после текущей работы.

## Сейчас

### 1. Завершить React migration

Stage 7 мигрирует оставшийся authenticated SSR вертикальными slices:

1. account detail/ledger;
2. import documents and mapping;
3. reports;
4. properties, categories и transaction rules;
5. workspaces, profile и остальные authenticated surfaces.

На каждом cutover:

- backend остаётся владельцем financial/security rules;
- historical GET может временно redirect в React;
- legacy mutation routes/templates/presenters удаляются;
- browser flow проходит на desktop, tablet и mobile.

Текущий детальный план:
[`Import documents and mapping`](../frontend/plan/import-documents-and-mapping/README.md).

### 2. Сохранить надёжность imports

- расширять только sanitized parser fixtures;
- улучшать неизвестные выписки через deterministic analysis и mapping;
- ограничивать тяжёлые raw payloads в browser API;
- делать upload/mapping mutations идемпотентными;
- сохранять документ и parse attempt при ошибке.

### 3. Упростить эксплуатацию

- production-shaped deployment и security checks;
- понятные backup/restore для PostgreSQL и upload storage;
- короткий alpha flow;
- диагностика без утечки raw financial data.

## Следом

После полного authenticated cutover:

- единый routing cutover без временного `/app` prefix;
- финальная очистка Jinja/HTMX/Alpine и legacy global CSS;
- улучшение account/report flows на основе реального использования;
- измерение производительности больших imports и reports;
- более ясная correction/audit UX для confirmed operations;
- укрепление workspace membership и invitation flows.

## Потом, при подтверждённой потребности

- расширение parser coverage;
- scheduled reminders и узкие chat workflows;
- правила с более точными условиями;
- долговые accounts и разделение principal/interest;
- связанные, но строго изолированные движения между workspaces;
- дополнительные property analytics поверх подтверждённого ledger.

Эти идеи не являются разрешением заранее расширять data model.

## Не планируем без отдельного product decision

- внешнюю AI-обработку выписок;
- ERP/CRM/property-management platform;
- tax/accounting suite;
- инвестиционный терминал;
- multi-frontend или microfrontend architecture;
- background infrastructure без измеренной необходимости;
- permissive cross-origin API.

## Постоянные ограничения

1. Raw imported data не теряется.
2. Parser/mapping не создаёт confirmed ledger records.
3. Transfer не влияет на profit.
4. Money хранится как `Decimal`/`Numeric`.
5. Workspace-owned queries всегда scoped.
6. Duplicate/retry не удваивает деньги.
7. Приватные данные не уходят во внешние сервисы без явного решения.

## Текущие технические риски

- upload и reparse пока синхронны;
- upload и mapping import требуют явных retry/idempotency contracts;
- часть authenticated UI ещё работает через SSR/HTMX;
- legacy HTMX reads могут иметь stale-response race до их React cutover;
- большие raw tables и review queues требуют bounded rendering/payloads.

Риск переносится в отдельную задачу только если подтверждён кодом или
измерением. Completed investigations не хранятся отдельными вечными audit
документами.
