# Booker Tee User Guide

Статус: краткая карта текущего продукта.

Основные подсказки должны находиться внутри интерфейса. Этот документ объясняет
термины и end-to-end flow, а не дублирует каждую кнопку.

## Основные понятия

- **Workspace** — отдельное пространство финансовых данных.
- **Account** — карта, счёт, наличные или другое место денег.
- **Operation** — доход, расход, перевод или корректировка.
- **Money entry** — движение суммы по account.
- **Category** — причина дохода/расхода.
- **Property** — необязательная привязка к объекту.
- **Import document** — сохранённая выписка.
- **Raw transaction** — строка выписки до подтверждения.

## Первый запуск

1. Создайте или выберите workspace.
2. Добавьте account с валютой и начальным балансом.
3. При необходимости создайте categories/properties.
4. Добавьте ручную операцию или загрузите выписку.

## Ручная операция

В Manual Ledger:

- income увеличивает account и profit;
- expense уменьшает account и profit;
- transfer перемещает деньги между двумя accounts и не меняет profit.

Проверяйте account, дату, валюту, сумму и category до подтверждения.

## Импорт выписки

```text
upload -> extraction -> mapping при необходимости -> review -> ledger
```

- Исходный файл сохраняется до разбора.
- Известный формат обычно сразу создаёт reviewable rows.
- Неизвестный формат требует выбрать таблицу и сопоставить колонки.
- Ошибка parser не удаляет документ.
- Повторная загрузка может найти duplicates.

## Review

Для каждой строки сравните raw source и normalized result:

- operation type;
- account;
- category/property;
- date, amount и currency;
- duplicate warning;
- transfer candidate.

Подтверждение создаёт ledger operation. Ignore и duplicate не влияют на
balances. Не подтверждайте сомнительную строку только ради завершения очереди.

## Исправления

- Draft/manual operation можно редактировать в пределах доступных действий.
- Confirmed manual operation изменяется через явный edit/cancel/restore
  workflow.
- Документ со связанными operations нельзя бездумно удалить.
- Если действие запрещено, интерфейс должен показать причину.

## Workspace and privacy

- Всегда проверяйте выбранный workspace.
- Viewer и manager имеют разные capabilities.
- Не загружайте реальные документы в публичные demo/test environments.
- Не отправляйте raw statements в issue tracker или внешний AI.

## Reports

Reports строятся по confirmed operations:

- transfer не входит в income/expense/profit;
- ignored/duplicate/review rows не входят в official totals;
- account balance и profit отвечают на разные вопросы.
