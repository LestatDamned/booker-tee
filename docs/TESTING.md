# Backend testing strategy

Статус: действующая стратегия Python/FastAPI-тестов Booker Tee. Первый цикл
рефакторинга завершён 21 августа 2026 года.

Документ определяет:

1. какие проверки нужны проекту;
2. на каком уровне должно проверяться поведение;
3. как уменьшать тестовый код без потери финансовых и security-инвариантов;
4. как анализировать и безопасно удалять пересекающиеся тесты.

Frontend/Vitest рассматривается отдельно. Здесь речь только о Python, FastAPI,
pytest, SQLAlchemy и PostgreSQL.

## Результат первого цикла

Рефакторинг устранил главный bottleneck — повторное создание FastAPI app — и
сократил setup-код, одновременно расширив проверяемое поведение.

| Метрика                    | До      | После                      |
| -------------------------- | ------: | --------------------------: |
| Собранные backend-сценарии |   1 110 |                       1 325 |
| Локальный backend-прогон   | 107,41 с | 12,90 с; 40 PostgreSQL skip |
| Прогон с PostgreSQL        |       — |          1 325 за 21,71 с |
| API subset                 | 78,51 с |            318 за 7,82 с |
| Python test code           |  43 861 |               42 741 строк |
| Строк на collected case    |    39,5 |                       32,3 |
| Parametrize-группы         |      51 |                        142 |
| Обычные asyncio markers    |     322 |                          0 |
| `create_async_engine()`    |      35 |                          1 |

Абсолютная квота строк больше не используется как цель: за время цикла продукт
и suite выросли на 215 сценариев, а общий тестовый код всё равно уменьшился.
Полезнее следить за повторяющимся Arrange, временем прогона и строками на
проверяемый случай, не удаляя тесты ради метрики.

## Основные принципы

### Проверять поведение

pytest описывает тест как Arrange → Act → Assert → Cleanup. Главное —
наблюдаемый результат поведения, а не внутренняя причина его получения. У теста
должно быть одно основное действие, а assertions должны описывать результат.

Источник: [pytest: Anatomy of a test](https://docs.pytest.org/en/stable/explanation/anatomy.html).

Interaction assertions допустимы на границах router/service/repository. Domain
test не должен фиксировать внутренний порядок вызовов, если итог можно проверить
напрямую.

### Переиспользовать Arrange осознанно

Fixtures дают явный, модульный и воспроизводимый контекст. Factory fixture
подходит, когда одному тесту нужны варианты объекта. Fixture не должна скрывать
важные финансовые условия или превращаться в глобальную систему неявного
состояния.

Источники:

- [pytest: About fixtures](https://docs.pytest.org/en/stable/explanation/fixtures.html);
- [pytest: How to use fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html#factories-as-fixtures).

Для Booker Tee предпочтительны feature-local fixtures и typed builders. Общий
`tests/conftest.py` содержит только инфраструктуру, нужную многим features.
Helper выносится только после повторения стабильного контракта минимум в трёх
местах.

### Параметризовать одинаковое поведение

Если Arrange, Act и Assert одинаковы, а меняются только вход и ожидаемый
результат, используется `pytest.mark.parametrize` с понятными `id`.

Источник: [pytest: parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html).

Разные бизнес-поведения не объединяются в одну таблицу только ради уменьшения
числа функций. Цикл с несколькими действиями не заменяет параметризацию: при
падении должен быть виден конкретный сценарий.

### Держать немного дорогих верхнеуровневых тестов

Проверка располагается на самом низком уровне, который надёжно обнаруживает
дефект. Integration tests проверяют соединение нескольких компонентов;
end-to-end tests остаются для критичных потоков.

Источник: [Google Testing Blog: Testing Pyramid](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html).

Это не разрешает удалять route-specific auth/capability checks: отсутствие
dependency на конкретном route не обнаружит unit test самой dependency.

### FastAPI: реальная HTTP-граница и управляемые overrides

Canonical FastAPI app имеет module scope. TestClient остаётся function-scoped
context manager, чтобы cookies и headers не протекали между тестами, а lifespan
выполнялся корректно. Function-scoped fixture очищает
`app.dependency_overrides` до и после каждого теста.

Settings, middleware, lifespan и специальная router composition создают
отдельный app, когда конфигурация приложения является предметом теста. Кэшировать
production `create_app()` нельзя: FastAPI app изменяемый.

Источники:

- [FastAPI: Testing](https://fastapi.tiangolo.com/tutorial/testing/);
- [FastAPI: dependency overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/);
- [FastAPI: lifespan tests](https://fastapi.tiangolo.com/advanced/testing-events/);
- [FastAPI: async tests](https://fastapi.tiangolo.com/advanced/async-tests/);
- [Starlette: TestClient](https://www.starlette.io/testclient/);
- [pytest: fixture scopes](https://docs.pytest.org/en/stable/how-to/fixtures.html#scope-sharing-fixtures-across-classes-modules-packages-or-session).

Canonical OpenAPI schema создаётся один раз session-scoped fixture.

### Async tests: не писать лишний marker

При `asyncio_mode = "auto"` pytest-asyncio сам обрабатывает async test functions.
`@pytest.mark.asyncio` нужен только для нестандартного `loop_scope`.

Источник: [pytest-asyncio markers](https://pytest-asyncio.readthedocs.io/en/stable/reference/markers/).

### PostgreSQL: rollback отдельно от concurrency

Обычные repository/integration tests используют общий engine и session,
присоединённую к внешней транзакции через SAVEPOINT; после теста транзакция
откатывается. Concurrency, commit, lock и idempotency tests используют
независимые sessions и реальные commits.

Источник: [SQLAlchemy: Joining a Session into an external transaction](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites).

Нельзя заменять конкурентный PostgreSQL-сценарий unit fake или одной session:
так теряется проверяемая race condition.

### Test doubles должны замечать изменение интерфейса

Для простых портов используются `create_autospec` или `spec_set`. Stateful fake
остаётся предпочтительным, когда тесту нужны связанные результаты, история
вызовов или изменение состояния.

Источник: [Python: unittest.mock autospeccing](https://docs.python.org/3/library/unittest.mock.html#autospeccing).

Свободный MagicMock или `SimpleNamespace` не должен скрывать рассинхронизацию с
production API. В то же время autospec не нужен для маленького value-like stub,
который явно реализует проверяемый protocol.

## Ответственность уровней

| Уровень               | Что проверять                                                   | Что не повторять                 |
| --------------------- | --------------------------------------------------------------- | -------------------------------- |
| Pure domain           | money rules, state transitions, validation, dedupe fingerprints | HTTP, SQLAlchemy и wiring        |
| Application/service   | workflow, transaction boundary, idempotency, orchestration      | все варианты HTTP envelope       |
| Repository/PostgreSQL | workspace filters, constraints, locks, races, real Decimal/SQL  | domain validation matrix         |
| FastAPI route         | auth, capability, parsing, DTO, status/error contract           | все domain branches              |
| App/smoke             | router registration, middleware, critical composition           | каждый edge case каждого feature |
| Production/release    | migrations, startup, health, backup/restore                     | unit-level calculations          |

Одно поведение может иметь несколько тестов, только если каждый уровень
страхует собственную границу.

## Обязательный анализ каждого теста

Перед упрощением, переносом или удалением нужно ответить:

1. Какое наблюдаемое поведение проверяет тест?
2. Какую границу и какой риск Booker Tee он защищает?
3. Поймает ли падение реальный дефект, важный проекту?
4. Есть ли уникальная ценность или поведение уже надёжно защищено на подходящем
   уровне?
5. Следует тест сохранить, упростить, параметризовать или рассматривать как
   кандидата на удаление?

Ускорение setup не меняет смысл теста. Изменение assertions, уровня проверки
или числа случаев требует повторного анализа. В отчёте по каждой партии кратко
указываются защищаемые поведения и решения по затронутым тестам.

## Что нельзя сокращать без равноценной замены

- internal transfer не влияет на profit;
- confirmed income/expense корректно влияет на balance и profit;
- workspace isolation и masking чужих идентификаторов;
- authentication, CSRF, session rotation и role capabilities;
- сохранение uploaded document, raw rows и parse attempts при ошибках;
- dedupe и idempotency, включая database race;
- optimistic locking и конкурентные owner/member transitions;
- Decimal/Numeric и currency semantics;
- migration, backup/restore и production preflight;
- отсутствие утечки private financial data.

Количество строк или длительность сами по себе не являются причиной удаления
такого теста.

## Безопасный протокол удаления теста

Тест можно удалить только если выполнены все условия:

1. Названо конкретное защищаемое поведение.
2. Указан остающийся тест, падающий при нарушении этого поведения.
3. Удаляемый тест не является единственной проверкой отдельной границы.
4. Это не единственная financial, workspace, security, privacy или concurrency
   проверка.
5. До и после изменения проходят relevant feature tests.
6. Полный suite с PostgreSQL проходит перед merge.

Для спорного удаления сначала вне основной ветки вносится минимальная ошибка в
защищаемое поведение. Если остающийся тест не падает, прежний тест удалять
нельзя. Полный mutation framework для этого не требуется.

Coverage может показать непройденный код, но не доказывает качество assertions
и не является основанием для удаления теста.

## Постоянные правила

- bug fix оставляет минимальный regression test на самом низком достаточном
  уровне;
- API endpoint получает contract/auth/capability checks, но не копию всей
  domain matrix;
- helper не выносится до появления стабильного повторения;
- тест длиннее 40 строк запускает review Arrange и test-double setup;
- status/role/error matrices с одинаковым Act/Assert параметризуются;
- PostgreSQL race tests сохраняют реальные независимые транзакции;
- полный suite периодически запускается с `--durations`;
- `strict_config`, `strict_markers`, `strict_parametrization_ids` и
  `strict_xfail` остаются включёнными;
- новые dependencies для xdist, coverage или mutation testing добавляются
  только после измеренного недостатка текущего набора.

## Команды измерения и локального цикла

```bash
# Количество случаев
uv run pytest --collect-only -q

# Полный локальный профиль
uv run pytest -q --durations=40 --durations-min=0.05

# Быстрый feature feedback
uv run pytest tests/features/<feature> -q -x

# Только прошлые падения / сначала прошлые падения
uv run pytest --lf
uv run pytest --ff

# API и PostgreSQL release checks
uv run pytest tests/api -q
BOOKER_TEE_TEST_DATABASE_URL=<test-database-url> uv run pytest -q
```

`--durations`, `--lf` и `--ff` входят в pytest; дополнительные зависимости не
нужны.
