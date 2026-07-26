import type {
  ImportMappingCommand,
  ImportMappingControlTotalCell,
  ImportMappingDto,
} from "./api/import-mapping-api";
import styles from "./import-mapping-page.module.css";

export type ControlTotalKind = "opening_balance" | "closing_balance";

export function ControlTotalMapping({
  activeKind,
  command,
  disabled,
  mapping,
  onChange,
  onSelectKind,
}: {
  activeKind: ControlTotalKind | null;
  command: ImportMappingCommand;
  disabled: boolean;
  mapping: ImportMappingDto;
  onChange: (command: ImportMappingCommand) => void;
  onSelectKind: (kind: ControlTotalKind | null) => void;
}) {
  return (
    <section
      aria-labelledby="control-totals-title"
      className={styles.controlTotalsPanel}
    >
      <header className={styles.controlTotalsHeader}>
        <div>
          <span className={styles.sectionLabel}>Проверка выписки</span>
          <h3 id="control-totals-title">Контрольные остатки</h3>
        </div>
        <p>
          Эти строки проверяют цепочку денег и не импортируются как операции.
        </p>
      </header>

      <div className={styles.controlTotalSlots}>
        <ControlTotalSlot
          active={activeKind === "opening_balance"}
          cell={command.openingBalanceCell ?? null}
          disabled={disabled}
          kind="opening_balance"
          mapping={mapping}
          onClear={() => onChange({ ...command, openingBalanceCell: null })}
          onSelect={() =>
            onSelectKind(
              activeKind === "opening_balance" ? null : "opening_balance",
            )
          }
        />
        <ControlTotalSlot
          active={activeKind === "closing_balance"}
          cell={command.closingBalanceCell ?? null}
          disabled={disabled}
          kind="closing_balance"
          mapping={mapping}
          onClear={() => onChange({ ...command, closingBalanceCell: null })}
          onSelect={() =>
            onSelectKind(
              activeKind === "closing_balance" ? null : "closing_balance",
            )
          }
        />
      </div>

      {activeKind ? (
        <div className={styles.cellPickerNotice} role="status">
          <strong>
            Выбираем{" "}
            {activeKind === "opening_balance"
              ? "начальный остаток"
              : "конечный остаток"}
          </strong>
          <span>
            Нажмите ячейку с суммой в таблице ниже. Можно перейти к следующим
            строкам таблицы.
          </span>
          <button type="button" onClick={() => onSelectKind(null)}>
            Отменить
          </button>
        </div>
      ) : null}
    </section>
  );
}

function ControlTotalSlot({
  active,
  cell,
  disabled,
  kind,
  mapping,
  onClear,
  onSelect,
}: {
  active: boolean;
  cell: ImportMappingControlTotalCell | null;
  disabled: boolean;
  kind: ControlTotalKind;
  mapping: ImportMappingDto;
  onClear: () => void;
  onSelect: () => void;
}) {
  const candidate = cell
    ? mapping.controlTotalCandidates.find(
        (item) => item.kind === kind && sameCell(item.cell, cell),
      )
    : null;
  const label = kind === "opening_balance" ? "Начало периода" : "Конец периода";
  return (
    <article
      className={styles.controlTotalSlot}
      data-active={active || undefined}
    >
      <div>
        <span>{label}</span>
        <strong>
          {candidate
            ? formatMoney(candidate.amount, candidate.currency)
            : cell
              ? "Выбрано в таблице"
              : "Не указан"}
        </strong>
        {cell ? (
          <small>
            {candidate ? "Найден автоматически · " : ""}
            стр. {cell.tableRef.pageNumber} · строка {cell.rowNumber} · колонка{" "}
            {cell.columnIndex + 1}
          </small>
        ) : (
          <small>Можно оставить пустым, если остатка в выписке нет.</small>
        )}
      </div>
      <div className={styles.controlTotalActions}>
        <button disabled={disabled} type="button" onClick={onSelect}>
          {cell ? "Изменить" : "Выбрать в таблице"}
        </button>
        {cell ? (
          <button disabled={disabled} type="button" onClick={onClear}>
            Убрать
          </button>
        ) : null}
      </div>
    </article>
  );
}

export function sameCell(
  left: ImportMappingControlTotalCell | null | undefined,
  right: ImportMappingControlTotalCell | null | undefined,
): boolean {
  return Boolean(
    left &&
    right &&
    left.tableRef.pageNumber === right.tableRef.pageNumber &&
    left.tableRef.tableIndex === right.tableRef.tableIndex &&
    left.rowNumber === right.rowNumber &&
    left.columnIndex === right.columnIndex,
  );
}

function formatMoney(amount: string, currency: string): string {
  const value = Number(amount);
  if (!Number.isFinite(value)) return `${amount} ${currency}`;
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(value);
}
