# Booker Tee Documentation

Статус: актуальный индекс документации.

Документация хранит только действующие решения и текущие планы. Завершённые
планы, миграционные снимки и superseded-спецификации удаляются: история остаётся
в Git.

## Как читать

Для любой задачи:

1. [`AGENTS.md`](../AGENTS.md);
2. этот индекс;
3. один профильный документ;
4. код и тесты как окончательная проверка фактического состояния.

Не загружайте все документы одновременно.

## Источники истины

| Область             | Документ                                                                                 | Когда читать                                    |
| ------------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Продукт             | [`PROJECT_VISION.md`](product/PROJECT_VISION.md)                                         | Scope, пользователи, продуктовые принципы       |
| Приоритеты          | [`ROADMAP.md`](product/ROADMAP.md)                                                       | Что делать после текущей задачи                 |
| Финансы             | [`DOMAIN_MODEL.md`](domain/DOMAIN_MODEL.md)                                              | Сущности, статусы, инварианты                   |
| Код                 | [`ARCHITECTURE.md`](architecture/ARCHITECTURE.md)                                        | Слои, границы features, transactions, security  |
| UI/UX               | [`DESIGN.md`](design/DESIGN.md)                                                          | Визуальный и interaction-контракт               |
| UI-компоненты       | [`UI_FOUNDATION.md`](design/UI_FOUNDATION.md)                                            | Что переиспользовать и как компоновать страницы |
| React/API           | [`REACT_FRONTEND_DESIGN.md`](design/REACT_FRONTEND_DESIGN.md)                            | Текущая browser-архитектура и cutover           |
| Формы               | [`FORM_DESIGN.md`](design/FORM_DESIGN.md)                                                | React form composition и accessibility          |
| Решения             | [`decisions/README.md`](architecture/decisions/README.md)                                | Принятые ADR                                    |
| Исполнение          | [`frontend/plan/README.md`](frontend/plan/README.md)                                     | Текущий migration stage                         |
| Рефакторинг imports | [`refactoring/imports/README.md`](refactoring/imports/README.md)                         | Активный план границ, этапов и тестов           |
| Рефакторинг ledger  | [`refactoring/ledger/TARGET_ARCHITECTURE.md`](refactoring/ledger/TARGET_ARCHITECTURE.md) | Transaction, DTO и module boundaries            |

## Операционные документы

- [`ALPHA_TESTING.md`](guides/ALPHA_TESTING.md) — локальный запуск и smoke flow.
- [`USER_GUIDE.md`](guides/USER_GUIDE.md) — короткая карта пользовательских
  сценариев и терминов.
- [`CHAT_INTEGRATIONS.md`](integrations/CHAT_INTEGRATIONS.md) — действующая
  граница Telegram/chat integration.
- [`UNKNOWN_STATEMENT_IMPORTER.md`](integrations/UNKNOWN_STATEMENT_IMPORTER.md) —
  fallback и mapping неизвестных выписок.

## Текущий frontend plan

Stages 0–6, Stage 7 Wave A и Wave B Properties/Categories завершены. Следующий
migration workflow — Transaction Rules.

- [`STAGE_07_MIGRATION_WAVES_AND_FINAL_CLEANUP.md`](frontend/plan/STAGE_07_MIGRATION_WAVES_AND_FINAL_CLEANUP.md)
- [`Reports migration`](frontend/plan/reports/README.md)
- [`Import documents and mapping`](frontend/plan/import-documents-and-mapping/README.md)
- [`Categories migration`](frontend/plan/categories/README.md)

## Правила поддержки

- Один факт имеет один основной документ.
- Кодовые имена, маршруты и статусы сверяются с текущим кодом.
- Completed plan сворачивается в короткую запись в index и удаляется.
- Новый документ создаётся только если у него есть отдельный долгоживущий
  consumer.
- Временные audits и measurements живут в task artifacts или Git history, а не
  в активном `docs/`.
- Битые ссылки и ссылки на удалённые реализации не допускаются.
