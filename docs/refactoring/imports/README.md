# Imports Refactoring

Статус: активная архитектурная миграция.

Единственный исполнимый план:
[`TARGET_ARCHITECTURE.md`](TARGET_ARCHITECTURE.md).

Он содержит:

- фактические и целевые границы `imports` / `import_review`;
- целевое дерево и карту перемещения файлов;
- ownership DTO, use cases, repositories и transactions;
- порядок миграции и текущий статус;
- обязательные safety/test gates;
- отложенный post-architecture backlog.

Исторические планы, аудиты и test-cleanup strategy поглощены в target.
Подробности завершённых этапов доступны в Git history и не поддерживаются как
параллельные источники истины.

## Текущая точка

```text
Шаг 0  documentation consolidation
  -> completed 2026-07-29

Safety baseline
  -> completed 2026-07-29: Ruff, ty, 601 tests

Шаг 1  review persistence ownership
  -> completed 2026-07-29

Шаг 2  duplicate evidence
  -> completed 2026-07-29

Шаг 3  documents
  -> completed 2026-07-29
  -> 3A read side completed 2026-07-29
  -> 3B lifecycle and persistence completed 2026-07-29
  -> 3C commands and infrastructure completed 2026-07-29

Шаг 4  statements
  -> completed 2026-07-29

Шаг 5  parsers and extractors
  -> 5A protocol, registry and extractors completed 2026-07-29
  -> 5B parser support completed 2026-07-29
  -> 5C bank parsers next
```

Перед массовыми moves не выполняется общая полировка старой структуры.
Исправляются только блокирующие dependency boundaries и отдельно
зафиксированные financial/data correctness risks.

## Неподвижные инварианты

1. Raw document, extraction payload, parse attempt и raw rows не теряются.
2. Parser и mapping не создают confirmed ledger records.
3. Workspace является обязательной границей каждого read/write.
4. Повторный upload, mapping или confirmation не удваивает деньги.
5. Transfer balanced и не влияет на profit.
6. Confirmed records не удаляются обычным document cleanup.
7. API не раскрывает sensitive source data.
8. Behavioral fix не смешивается с массовым file move.

## Проверки

Для каждого change set:

```bash
uv run ruff check .
uv run ty check
uv run pytest tests/features/imports -q
```

PostgreSQL, API, chat и frontend checks добавляются по затронутому capability,
как описано в target.
