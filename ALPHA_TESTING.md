# Альфа-тестирование Booker Tee

Это короткая инструкция для локального альфа-теста. Она рассчитана на людей,
которые не обязаны быть программистами.

## Что нужно тестировщику

- Установленный и запущенный Docker Desktop.
- Локальная копия этого репозитория.
- Файл банковской выписки, который человек готов проверить локально.

Booker Tee обрабатывает загруженные файлы локально. Не отправляйте реальные
выписки в чат, почту, баг-репорты, скриншоты или GitHub issues.

## Запуск одной командой

macOS или Linux:

```bash
./scripts/alpha-up.sh
```

Windows PowerShell:

```powershell
.\scripts\alpha-up.ps1
```

Для запуска в фоне:

macOS или Linux:

```bash
./scripts/alpha-up.sh --detach
```

Windows PowerShell:

```powershell
.\scripts\alpha-up.ps1 --detach
```

Если порт `8000` уже занят, выберите другой:

macOS или Linux:

```bash
BOOKER_TEE_APP_PORT=8010 ./scripts/alpha-up.sh --detach
```

Windows PowerShell:

```powershell
$env:BOOKER_TEE_APP_PORT = "8010"; .\scripts\alpha-up.ps1 --detach
```

Затем откройте порт из сообщения скрипта. Обычно это:

```text
http://127.0.0.1:8000
```

Первый запуск может занять несколько минут: Docker собирает образ приложения и
устанавливает зависимости. Следующие запуски обычно быстрее.

Чтобы остановить приложение, нажмите `Ctrl+C` в терминале, где оно запущено.
Также можно остановить его отдельной командой:

macOS или Linux:

```bash
./scripts/alpha-down.sh
```

Windows PowerShell:

```powershell
.\scripts\alpha-down.ps1
```

Если нужно начать заново и удалить локальную тестовую базу, загрузки и кеш
окружения, используйте reset-команду:

macOS или Linux:

```bash
./scripts/alpha-reset.sh --yes
```

Windows PowerShell:

```powershell
.\scripts\alpha-reset.ps1 --yes
```

## Первый сценарий проверки

1. Откройте приложение и создайте пользователя.
2. Проверьте, что рабочее пространство уже есть, или создайте новое.
3. Создайте хотя бы один счет для выписки, которую хотите импортировать.
4. Загрузите банковскую выписку в формате PDF или XLSX.
5. Откройте импортированный документ и проверьте, извлеклись ли строки.
6. Разберите несколько строк:
   - подтвердите реальный доход или расход;
   - отметьте внутренний перевод как перевод, если такая строка есть;
   - проигнорируйте строку, которая не должна попадать в отчеты;
   - загрузите ту же выписку повторно и проверьте предупреждения о дублях.
7. Откройте отчеты и страницы счетов, чтобы проверить, изменились ли балансы и
   итоги после подтверждения строк.

## Какую обратную связь собрать

Попросите тестировщиков коротко ответить на вопросы:

- Где они застряли?
- Какие слова, статусы или подписи были непонятны?
- Выглядел ли процесс загрузки и проверки выписки надежным?
- Были ли строки с неправильной датой, суммой, знаком, валютой или описанием?
- Было ли понятно, чем перевод отличается от дохода или расхода?
- Совпали ли отчеты с ожиданиями после подтверждения строк?
- Что они первым делом захотели сделать, но не смогли?

## Границы альфы

- Это локальная альфа, а не hosted-продукт.
- Это не налоговая система, не бухгалтерская отчетность, не payroll и не ERP.
- Надежность парсера зависит от банка и формата выписки.
- Сейчас явно поддержаны PDF/XLSX и автоопределение для Альфа-Банк XLSX,
  Ozon Банк, T-Банк, Сбербанк, ВТБ и Экспобанк.
- Реальные банковские файлы должны оставаться локально, их нельзя коммитить.

---

# Booker Tee Alpha Testing

This is a short guide for local alpha testing. It is written for people who do
not need to be programmers.

## What testers need

- Docker Desktop installed and running.
- A local copy of this repository.
- A bank statement file they are comfortable testing locally.

Booker Tee processes uploaded files locally. Do not send real statements in
chat, email, bug reports, screenshots, or GitHub issues.

## One-command start

macOS or Linux:

```bash
./scripts/alpha-up.sh
```

Windows PowerShell:

```powershell
.\scripts\alpha-up.ps1
```

To start in the background:

macOS or Linux:

```bash
./scripts/alpha-up.sh --detach
```

Windows PowerShell:

```powershell
.\scripts\alpha-up.ps1 --detach
```

If port `8000` is already busy, choose another one:

macOS or Linux:

```bash
BOOKER_TEE_APP_PORT=8010 ./scripts/alpha-up.sh --detach
```

Windows PowerShell:

```powershell
$env:BOOKER_TEE_APP_PORT = "8010"; .\scripts\alpha-up.ps1 --detach
```

Then open the port printed by the script. Usually this is:

```text
http://127.0.0.1:8000
```

The first run can take a few minutes because Docker builds the application image
and installs dependencies. Later starts should usually be faster.

To stop the app, press `Ctrl+C` in the terminal where it is running.
You can also stop it with a separate command:

macOS or Linux:

```bash
./scripts/alpha-down.sh
```

Windows PowerShell:

```powershell
.\scripts\alpha-down.ps1
```

If you need a clean start and want to delete the local test database, uploads,
and cached environment, use the reset command:

macOS or Linux:

```bash
./scripts/alpha-reset.sh --yes
```

Windows PowerShell:

```powershell
.\scripts\alpha-reset.ps1 --yes
```

## First test script

1. Open the app and create a user.
2. Check that a workspace exists or create one.
3. Create at least one account for the statement you want to import.
4. Upload a PDF or XLSX bank statement.
5. Open the imported document and check whether rows were extracted.
6. Review several rows:
   - confirm a real income or expense;
   - mark an internal transfer as transfer if applicable;
   - ignore a row that should not affect reports;
   - upload the same statement again and check duplicate warnings.
7. Open reports and account screens to see whether confirmed rows changed
   balances and totals.

## Feedback to collect

Ask testers to write short notes for these questions:

- Where did they get stuck?
- Which words, statuses, or labels were unclear?
- Did the upload and review flow feel trustworthy?
- Did any extracted row have a wrong date, amount, sign, currency, or
  description?
- Was it clear how transfers differ from income or expense?
- Did reports match what they expected after confirming rows?
- What was the first thing they wanted to do but could not?

## Known alpha boundaries

- This is a local alpha, not a hosted product.
- It is not tax software, statutory accounting, payroll, or ERP.
- Parser reliability depends on the bank and statement format.
- Explicitly supported now: PDF/XLSX and automatic detection for Alfa Bank XLSX,
  Ozon Bank, T-Bank, Sberbank, VTB, and Expobank.
- Real bank files must stay local and should not be committed.
