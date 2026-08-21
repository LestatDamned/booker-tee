# Booker Tee documentation

Статус: индекс действующих документов.

Читайте `AGENTS.md`, этот индекс, один профильный документ, затем код и тесты.
Завершённые планы и аудиты не хранятся рядом с действующими контрактами: их
история остаётся в Git.

## Основные контракты

| Область          | Документ                                                      |
| ---------------- | ------------------------------------------------------------- |
| Продукт          | [`PROJECT_VISION.md`](product/PROJECT_VISION.md)              |
| Приоритеты       | [`ROADMAP.md`](product/ROADMAP.md)                            |
| Финансы          | [`DOMAIN_MODEL.md`](domain/DOMAIN_MODEL.md)                   |
| Архитектура      | [`ARCHITECTURE.md`](architecture/ARCHITECTURE.md)             |
| Тестирование     | [`TESTING.md`](TESTING.md)                                    |
| Принятые решения | [`architecture/decisions`](architecture/decisions/README.md)  |
| UI/UX            | [`DESIGN.md`](design/DESIGN.md)                               |
| React-композиция | [`UI_FOUNDATION.md`](design/UI_FOUNDATION.md)                 |
| React/API        | [`REACT_FRONTEND_DESIGN.md`](design/REACT_FRONTEND_DESIGN.md) |

## Feature contracts

- [`Debts`](features/debts/README.md) — principal, interest и проводки.
- [`Operations`](features/operations/README.md) — единый поток операций.
- [`Reports`](features/reports/README.md) — period reports и XLSX.
- [`Workspace collaboration`](features/workspaces/README.md) — роли,
  invitations, concurrency и activity.
- [`Chat integrations`](integrations/CHAT_INTEGRATIONS.md).
- [`Unknown statement importer`](integrations/UNKNOWN_STATEMENT_IMPORTER.md).

## Работа и эксплуатация

- [`COMMANDS.md`](COMMANDS.md) — команды разработки и эксплуатации.
- [`Production runbook`](deploy/plan/README.md).
- [`ALPHA_TESTING.md`](guides/ALPHA_TESTING.md).
- [`USER_GUIDE.md`](guides/USER_GUIDE.md).

## Правила поддержки

- Один факт имеет один основной документ.
- Новый документ создаётся только для отдельного долгоживущего consumer.
- Структуру файлов не пересказывают: её показывает код.
- Completed plan удаляется; незавершённый пункт переносится в roadmap или
  короткий активный план.
- Даты прогонов, списки удалённых файлов и implementation diary остаются в Git.
