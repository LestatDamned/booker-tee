# Alpha Testing

Статус: актуальный локальный smoke guide.

## Запуск

Требуются Docker и свободный порт `8000`.

macOS/Linux:

```bash
./scripts/alpha-up.sh
```

Windows PowerShell:

```powershell
.\scripts\alpha-up.ps1
```

Открыть `http://127.0.0.1:8000`.

Фоновый запуск:

```bash
./scripts/alpha-up.sh --detach
```

Другой порт:

```bash
BOOKER_TEE_APP_PORT=8010 ./scripts/alpha-up.sh --detach
```

Остановка:

```bash
./scripts/alpha-down.sh
```

Сброс локальных alpha data — destructive:

```bash
./scripts/alpha-reset.sh --yes
```

Не использовать reset для окружения с нужными данными.

## Smoke flow

1. Зарегистрироваться или войти.
2. Создать/выбрать workspace.
3. Создать account.
4. Добавить manual income и expense.
5. Создать internal transfer и проверить, что он не попал в profit.
6. Загрузить sanitized PDF/XLSX statement.
7. Проверить document status:
   - known parser ведёт к review;
   - unknown layout ведёт к mapping;
   - failure сохраняет document и attempt.
8. В Import Review классифицировать, подтвердить/игнорировать строки и проверить
   duplicate/transfer behavior.
9. Сверить account balance и reports.
10. Проверить mobile width и keyboard navigation на критической форме.

## Что сообщать

- URL и шаг;
- ожидаемый и фактический результат;
- browser/OS/viewport;
- screenshot без приватных данных;
- воспроизводимость;
- console/network error без tokens/raw statement content.

## Границы alpha

- Использовать только вымышленные или sanitized документы.
- Не считать alpha backup production backup.
- Chat integration выключена по умолчанию.
- Часть authenticated страниц ещё SSR, Manual Ledger и Import Review — React.
- Upload/reparse пока могут занимать request синхронно.
