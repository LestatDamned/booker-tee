# Imports Test Strategy

Статус: план оздоровления тестового набора.

## Диагноз

Исходный профильный набор на момент составления стратегии содержал 201 test и
около 8 190 строк. Все 201 тест проходили. Эта цифра — историческая точка
отсчёта, а не целевая метрика: после каждого шага важнее сохраняемые риски, чем
количество tests. Проблема набора была не в абсолютном количестве, а в
структуре:

- файлы по 600–850 строк смешивают разные capabilities и уровни;
- есть tests forwarding/test-only wrappers;
- одни и те же permission/error contracts повторяются по endpoint;
- много mapping cases проверяют всю цепочку preview → mapper → draft, хотя
  меняется одна pure policy;
- `test_imports.py` является несвязным catch-all;
- `test_user_guide_templates.py` лежит в imports, хотя тестирует dashboard,
  profile и workspaces;
- нет end-to-end сценария пересекающихся выписок; он сознательно отложен до
  последней фазы после структурного рефакторинга.

Следовательно, массово удалять тесты по количеству нельзя. Сначала их нужно
переклассифицировать по защищаемому риску.

## Почему предыдущий запуск завис

Зависание воспроизводилось на:

```text
test_upload_storage_preserves_pdf_bytes
  -> UploadStorage._save
  -> await UploadFile.read
  -> anyio.to_thread.run_sync
```

В sandbox `anyio.to_thread.run_sync()` не получал worker thread. Минимальный
пример также зависал. Тот же пример вне sandbox завершился сразу, а полный
профильный набор дал:

```text
201 passed, 1 warning in 12.70s
```

Это ограничение среды исполнения, не failure проекта и не признак лишнего
storage test.

Отдельно остаётся предупреждение о deprecated связке Starlette TestClient с
текущим httpx adapter. Оно не ломает тесты, но должно быть устранено обычным
dependency maintenance, а не подавлением warning.

## Четыре категории

### A — обязательные risk tests

Удалять нельзя. Они защищают деньги, ownership или сохранность источника:

- transfer не влияет на profit;
- confirmation создаёт ожидаемые Operation/MoneyEntry один раз;
- confirmed dedupe race guard;
- workspace isolation;
- upload/mapping/confirmation idempotency;
- raw document/text/tables/rows сохраняются;
- parser failure сохраняет document и attempt;
- delete/ignore не повреждают confirmed или linked rows;
- undo атомарно согласует ledger и review;
- mapping unsigned amount не получает опасный default;
- API не раскрывает sensitive source data.

Эти тесты должны проверять observable behavior и по возможности использовать
реальный PostgreSQL для concurrency/constraints.

### B — полезные pure policy tests

Сохранять компактными table-driven тестами:

- statement totals и balance chain;
- classification priority;
- confirmability;
- lifecycle transition matrix;
- queue ordering;
- parser fixture → normalized draft;
- mapping command validation;
- unknown statement column/table detection.

Один parametrized matrix предпочтительнее множества почти одинаковых tests,
если failure остаётся диагностируемым.

### C — contract tests

Нужны в ограниченном количестве:

- один happy-path schema test на endpoint family;
- один permission/workspace masking test на dependency/policy family;
- один typed validation/error mapping test;
- idempotency header/conflict test для mutation family.

Не нужно заново доказывать одинаковую workspace dependency на каждом endpoint,
если endpoint использует уже протестированную общую dependency и не добавляет
собственную lookup logic.

### D — implementation-detail tests

Кандидаты на удаление или переписывание:

- прямые tests test-only forwarding wrappers;
- tests точного внутреннего DTO graph без публичного контракта;
- tests private methods/fingerprints, если поведение покрыто replay/conflict;
- отдельный test `len(...)` wrapper;
- tests server workflow labels/steps, если это становится React concern;
- повторное прохождение одной mapping chain ради проверки одного helper.

## Решения по текущим файлам

| Current file | Решение |
| --- | --- |
| `test_imports.py` | Расформировать на storage, upload, deduplication и удалить legacy review-wrapper tests |
| ~~`test_user_guide_templates.py`~~ | ✅ Удалён из imports: сохранён один navigation contract у dashboard, семь layout/copy assertions удалены |
| `test_unknown_statement_analysis.py` | Разделить fixtures/integration и pure heuristics; убрать повторное mapping coverage |
| `test_unknown_statement_mapping.py` | Разделить command validation, row mapping, template compatibility; удалить wrapper tests |
| `test_import_parsers.py` | Сохранить fixture contract per parser, не тестировать каждый helper отдельно |
| `test_import_review_read_api.py` | Разделить read, lifecycle, confirmation, transfers/undo API contracts |
| `test_import_mapping_api.py` | Оставить bounded projection, conversion/error и idempotency contracts |
| Review domain tests | Сохранить, консолидировать matrices без потери reason-code assertions |
| Document list/detail tests | Сохранить capability/status matrices; убрать server-owned visual workflow после переноса в React |

## Выполненные удаления в Commit 2.1

Удалены tests, единственной целью которых были:

- `raw_transaction_status_for_review_action`;
- `RawTransactionReviewUseCase`;
- `mapped_rows_to_drafts`;
- `preview_unknown_statement_mapping`, если production использует compatible
  preview;
- `compatible_mapping_table_count`;
- `mapped_row_to_draft`;
- `raw_transaction_status_for_mapped_row`;
- `mapped_row_source_id`.

Полезные mapping assertions перенесены на public production actors:

```text
mapping preview/import
  вместо
helper A -> helper B -> private draft
```

Два теста `RawTransactionReviewUseCase` не переносились: они проверяли
production-unused orchestration wrapper. Действующий API-сценарий подтверждения
с сохранением правила покрывается тестами
`import_review/application/confirmation.py`.

## Выполненная очистка legacy UI tests

`test_user_guide_templates.py` удалён из imports suite:

- переход с dashboard в канонический React Import Review сохранён в
  `tests/features/dashboard/test_dashboard_template.py`;
- проверки точных CSS-классов, текстов onboarding, profile layout и полного
  workspace HTML удалены;
- invitation, membership, permissions и session behavior остаются покрыты
  тестами соответствующих `users` и `workspaces` services/policies.

Тест шаблона оставлен только там, где legacy dashboard пока является реальным
runtime consumer и связывает его с уже мигрированным React workflow.

## Выполненная замена private method tests

Два ledger test больше не вызывают внутренние методы
`ManualOperationWriter._get_manual_operation(...)` и
`ManualOperationWriter._replace_money_entries(...)`.

Сохранённые публичные сценарии проверяют:

- imported operation нельзя изменить через manual `update(...)`;
- обновление manual income в expense заменяет старую проводку, нормализует знак
  суммы и оставляет актуальный `operation.money_entries`.

Повторяющиеся команды update собираются одним узким test-data builder. Общих
repository/test-framework abstractions не добавлено.

## Недостающие tests основной части рефакторинга

Приоритетнее большинства текущих implementation tests:

1. concurrent mapping import;
2. upload lost-response replay с фактической persistence;
3. parse failure сохраняет document/attempt/source;
4. ~~document status transition matrix после удаления reparse;~~ completed in
   Phase 3.3;
5. confirmation и undo на реальной transaction boundary;
6. transfer `affects_profit=false`;
7. delete/ignore behavior при linked operations.

Тесты overlapping-statement deduplication, `MARK_UNIQUE` и конкурентного
confirmation добавляются в последней Phase 8. До неё существующее
deduplication behavior сохраняется без расширения.

## Целевая раскладка

```text
tests/features/imports/
  documents/
    test_upload.py
    test_management.py
    test_read_models.py
  statement_processing/
    test_parsers.py
    test_validation.py
    test_deduplication.py
    test_unknown_analysis.py
  mapping/
    test_validation.py
    test_preview.py
    test_import.py
    test_templates.py

tests/features/import_review/
  test_classification.py
  test_confirmability.py
  test_lifecycle.py
  test_confirmation.py
  test_transfers.py
  test_undo.py
  test_read_model.py

tests/api/
  imports/
  import_review/

tests/postgres/
  imports/
    test_mapping_idempotency.py
    test_overlapping_statement_deduplication.py
```

## Правило удаления

Тест можно удалить, если выполнено хотя бы одно условие:

1. production symbol удалён и тест не защищает отдельное поведение;
2. тот же observable contract уже проверяется на более устойчивой границе;
3. тест проверяет форму внутренней реализации, которую намеренно меняем;
4. тест находится не в своём feature и уже существует у фактического owner.

Нельзя удалять тест только потому, что он длинный, медленный или похож на
другой по setup. Сначала нужно назвать риск, который останется без защиты.

## Метрики успеха

Не ставить цель «уменьшить tests до N». Использовать:

- каждый P1/P2 financial/data risk имеет test;
- ни один production-unused wrapper не имеет отдельного test;
- test filename соответствует capability;
- common API dependency не проверяется заново без endpoint-specific behavior;
- pure policy suite выполняется быстро без DB;
- PostgreSQL suite мал, но покрывает constraints/concurrency;
- failure указывает на нарушенный бизнес-контракт, а не на случайный helper.
