# Alpha testing

Статус: локальный smoke guide для канонического React frontend.

## Запуск

```bash
./scripts/alpha-up.sh
# Windows: .\scripts\alpha-up.ps1
```

Открыть `http://127.0.0.1:8000`. Для фонового запуска добавить `--detach`.
Остановка: `./scripts/alpha-down.sh`.

Сброс локальных данных выполняется только намеренно:

```bash
./scripts/alpha-reset.sh --yes
```

## Smoke flow

1. Зарегистрироваться или войти и выбрать workspace.
2. Создать account.
3. Добавить income и expense.
4. Создать transfer и убедиться, что он не попал в profit.
5. Загрузить sanitized PDF/XLSX.
6. Проверить known parser, unknown mapping и безопасное сохранение failure.
7. Подтвердить, игнорировать и сопоставить строки Import Review.
8. Сверить operations, account balance и reports.
9. Проверить критическую форму с keyboard navigation и на mobile width.

В отчёте укажите URL, шаги, expected/actual result, browser, viewport и
воспроизводимость. Screenshots и console/network details не должны содержать
tokens, account identifiers или raw statement data.

Используйте только вымышленные или sanitized документы. Alpha backup не является
production backup; upload пока может выполняться синхронно.
