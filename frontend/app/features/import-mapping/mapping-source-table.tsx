import { useState } from "react";

import { Button } from "../../ui/button/button";
import type {
  ImportMappingCommand,
  ImportMappingControlTotalCell,
  ImportMappingSourceTable,
} from "./api/import-mapping-api";
import { loadImportMappingSourceRows } from "./api/import-mapping-api";
import { sameCell, type ControlTotalKind } from "./control-total-mapping";
import {
  assignMappingColumnRole,
  isRequiredMappingRole,
  mappingAmountMode,
  mappingColumnRoles,
  mappingRoleCanBeAssigned,
  mappingRoleForColumn,
  type MappingColumnRole,
  type MappingFieldErrors,
} from "./mapping-draft";
import styles from "./import-mapping-page.module.css";

const roleLabels: Record<MappingColumnRole, string> = {
  operationDateColumn: "Дата операции",
  postingDateColumn: "Дата проводки",
  descriptionColumn: "Описание",
  amountColumn: "Сумма",
  debitAmountColumn: "Списание",
  creditAmountColumn: "Зачисление",
  currencyColumn: "Валюта",
  balanceAfterColumn: "Остаток",
};

export function MappingSourceTable({
  command,
  disabled,
  documentId,
  errors,
  onSelectControlTotal,
  selectionKind,
  onChange,
  table,
}: {
  command: ImportMappingCommand;
  disabled: boolean;
  documentId: string;
  errors: MappingFieldErrors;
  onChange: (command: ImportMappingCommand) => void;
  onSelectControlTotal: (cell: ImportMappingControlTotalCell) => void;
  selectionKind: ControlTotalKind | null;
  table: ImportMappingSourceTable;
}) {
  const [visibleRows, setVisibleRows] = useState(table.sampleRows);
  const [windowStart, setWindowStart] = useState(1);
  const [hasPrevious, setHasPrevious] = useState(false);
  const [hasNext, setHasNext] = useState(
    table.rowCount > table.sampleRows.length,
  );
  const [rowsPending, setRowsPending] = useState(false);
  const [rowsError, setRowsError] = useState<string | null>(null);
  const amountMode = mappingAmountMode(command);
  const options = mappingRoleOptions(amountMode);
  const missingErrors = Object.entries(errors).filter(
    ([field]) =>
      mappingColumnRoles.includes(field as MappingColumnRole) &&
      !mappingColumnRoles.some(
        (role) => role === field && command[role] != null,
      ),
  );

  const loadWindow = async (startRowNumber: number) => {
    if (rowsPending) return;
    setRowsPending(true);
    setRowsError(null);
    const result = await loadImportMappingSourceRows({
      documentId,
      startRowNumber,
      tableRef: table.ref,
    });
    setRowsPending(false);
    if (result.status === "unauthenticated") {
      window.location.assign(
        `/login?next=${encodeURIComponent(window.location.pathname)}`,
      );
      return;
    }
    if (result.status !== "success") {
      setRowsError(
        result.status === "not_found"
          ? "Исходная таблица больше недоступна."
          : result.status === "error"
            ? result.message
            : "Не удалось загрузить исходные строки.",
      );
      return;
    }
    setVisibleRows(result.source.rows);
    setWindowStart(result.source.startRowNumber);
    setHasPrevious(result.source.hasPrevious);
    setHasNext(result.source.hasNext);
  };

  return (
    <section className={styles.sourcePanel} aria-labelledby="source-title">
      <header className={styles.sourceHeader}>
        <div>
          <span className={styles.sectionLabel}>Источник</span>
          <h3 id="source-title">Таблица выписки</h3>
        </div>
        <div className={styles.sourceMeta} aria-label="Параметры таблицы">
          <span>Страница {table.ref.pageNumber}</span>
          <span>
            {table.rowCount} строк · {table.columnCount} колонок
          </span>
          {table.isContinuation ? <span>Продолжение</span> : null}
        </div>
      </header>

      {table.suggestion ? (
        <details className={styles.suggestion}>
          <summary>Почему роли заполнены так</summary>
          <div>
            <p>
              Роли предложены анализатором. Сверьте их с исходными значениями
              перед предпросмотром.
            </p>
            {table.suggestion.reasons.length > 0 ? (
              <ul>
                {table.suggestion.reasons.map((reason) => (
                  <li key={`${reason.field}-${reason.columnIndex}`}>
                    {mappingFieldLabel(reason.field)} — колонка{" "}
                    {reason.columnIndex + 1}
                    {reason.header ? ` «${reason.header}»` : ""}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </details>
      ) : null}

      {missingErrors.length > 0 ? (
        <div className={styles.missingRoles} role="status">
          Назначьте обязательные роли:{" "}
          {missingErrors
            .map(([field]) => roleLabels[field as MappingColumnRole])
            .join(", ")}
          .
        </div>
      ) : null}

      {selectionKind ? (
        <p className={styles.tableSelectionHint}>
          Выберите ячейку с суммой{" "}
          {selectionKind === "opening_balance" ? "начального" : "конечного"}{" "}
          остатка. Выбранная строка будет исключена из операций.
        </p>
      ) : null}

      <div
        className={styles.sourceViewport}
        id="mapping-roles"
        tabIndex={0}
        aria-label="Роли колонок и исходные строки таблицы"
      >
        <table>
          <caption>
            Настройка ролей колонок и исходные строки без преобразования
          </caption>
          <thead>
            <tr className={styles.mappingRoleRow}>
              <th className={styles.rowNumberHeader} scope="col">
                Строка
              </th>
              {Array.from({ length: table.columnCount }, (_, columnIndex) => {
                const role = mappingRoleForColumn(command, columnIndex);
                const error = role ? errors[role] : undefined;
                const header = sourceColumnHeader(table, command, columnIndex);
                const selectId = role ?? `mapping-role-${columnIndex}`;
                return (
                  <th
                    data-assigned={Boolean(role) || undefined}
                    data-required={
                      role
                        ? isRequiredMappingRole(role, amountMode) || undefined
                        : undefined
                    }
                    key={columnIndex}
                    scope="col"
                  >
                    <label htmlFor={selectId}>
                      <span>Колонка {columnIndex + 1}</span>
                      {header ? <small title={header}>{header}</small> : null}
                    </label>
                    <select
                      id={selectId}
                      aria-describedby={
                        error && role ? `${role}-error` : undefined
                      }
                      aria-invalid={Boolean(error)}
                      aria-label={`Роль колонки ${columnIndex + 1}${header ? `, ${header}` : ""}`}
                      data-mapping-role-select
                      disabled={disabled}
                      value={role ?? ""}
                      onChange={(event) =>
                        onChange(
                          assignMappingColumnRole(
                            command,
                            columnIndex,
                            (event.target.value ||
                              null) as MappingColumnRole | null,
                          ),
                        )
                      }
                    >
                      <option
                        disabled={
                          role ? isRequiredMappingRole(role, amountMode) : false
                        }
                        value=""
                      >
                        Не используется
                      </option>
                      <optgroup label="Обязательные роли">
                        {options.required.map((option) => (
                          <option
                            disabled={
                              !mappingRoleCanBeAssigned(
                                command,
                                columnIndex,
                                option,
                              )
                            }
                            key={option}
                            value={option}
                          >
                            {roleLabels[option]}
                          </option>
                        ))}
                      </optgroup>
                      <optgroup label="Дополнительные роли">
                        {options.optional.map((option) => (
                          <option
                            disabled={
                              !mappingRoleCanBeAssigned(
                                command,
                                columnIndex,
                                option,
                              )
                            }
                            key={option}
                            value={option}
                          >
                            {roleLabels[option]}
                          </option>
                        ))}
                      </optgroup>
                    </select>
                    <span className={styles.roleKind}>
                      {role
                        ? isRequiredMappingRole(role, amountMode)
                          ? "Обязательная роль"
                          : "Дополнительная роль"
                        : "Роль не назначена"}
                    </span>
                    {error && role ? (
                      <span
                        className={styles.columnRoleError}
                        id={`${role}-error`}
                      >
                        {error}
                      </span>
                    ) : null}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr
                data-control-row={
                  rowContainsControlTotal(command, table, row.rowNumber) ||
                  undefined
                }
                data-start={
                  row.rowNumber === command.firstDataRowNumber || undefined
                }
                key={row.rowNumber}
              >
                <th scope="row">{row.rowNumber}</th>
                {Array.from({ length: table.columnCount }, (_, columnIndex) => {
                  const cell: ImportMappingControlTotalCell = {
                    tableRef: table.ref,
                    rowNumber: row.rowNumber,
                    columnIndex,
                  };
                  const selectedKind = selectedControlTotalKind(command, cell);
                  const value = row.cells[columnIndex];
                  return (
                    <td
                      data-control-cell={selectedKind ?? undefined}
                      key={columnIndex}
                    >
                      {selectionKind && value ? (
                        <button
                          aria-label={`Выбрать ячейку: строка ${row.rowNumber}, колонка ${columnIndex + 1}, значение ${value}`}
                          className={styles.selectableCell}
                          disabled={disabled}
                          type="button"
                          onClick={() => onSelectControlTotal(cell)}
                        >
                          {value}
                        </button>
                      ) : (
                        value || <span className={styles.emptyCell}>—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rowsError ? (
        <p className={styles.sourceRowsError} role="alert">
          {rowsError}
        </p>
      ) : null}
      {table.rowCount > visibleRows.length ? (
        <div className={styles.sourcePagination}>
          <p className={styles.boundedNote}>
            Строки {visibleRows[0]?.rowNumber ?? 0}–
            {visibleRows.at(-1)?.rowNumber ?? 0} из {table.rowCount}. Итоги
            рассчитываются по всему документу.
          </p>
          <div>
            <Button
              disabled={!hasPrevious || rowsPending}
              tone="secondary"
              type="button"
              onClick={() => void loadWindow(Math.max(1, windowStart - 30))}
            >
              Назад
            </Button>
            <Button
              disabled={!hasNext || rowsPending}
              tone="secondary"
              type="button"
              onClick={() =>
                void loadWindow(
                  (visibleRows.at(-1)?.rowNumber ?? windowStart) + 1,
                )
              }
            >
              {rowsPending ? "Загрузка…" : "Дальше"}
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function selectedControlTotalKind(
  command: ImportMappingCommand,
  cell: ImportMappingControlTotalCell,
): ControlTotalKind | null {
  if (sameCell(command.openingBalanceCell, cell)) return "opening_balance";
  if (sameCell(command.closingBalanceCell, cell)) return "closing_balance";
  return null;
}

function rowContainsControlTotal(
  command: ImportMappingCommand,
  table: ImportMappingSourceTable,
  rowNumber: number,
): boolean {
  return [command.openingBalanceCell, command.closingBalanceCell].some(
    (cell) =>
      cell?.tableRef.pageNumber === table.ref.pageNumber &&
      cell.tableRef.tableIndex === table.ref.tableIndex &&
      cell.rowNumber === rowNumber,
  );
}

function mappingRoleOptions(amountMode: "single" | "split"): {
  required: MappingColumnRole[];
  optional: MappingColumnRole[];
} {
  return {
    required:
      amountMode === "single"
        ? ["operationDateColumn", "descriptionColumn", "amountColumn"]
        : [
            "operationDateColumn",
            "descriptionColumn",
            "debitAmountColumn",
            "creditAmountColumn",
          ],
    optional: ["postingDateColumn", "currencyColumn", "balanceAfterColumn"],
  };
}

function sourceColumnHeader(
  table: ImportMappingSourceTable,
  command: ImportMappingCommand,
  columnIndex: number,
): string {
  const headerRow =
    table.sampleRows.find(
      (row) => row.rowNumber === command.firstDataRowNumber - 1,
    ) ?? table.sampleRows[0];
  return (
    table.candidates.find(
      (candidate) =>
        candidate.columnIndex === columnIndex && candidate.header.trim(),
    )?.header ??
    headerRow?.cells[columnIndex]?.trim() ??
    ""
  );
}

function mappingFieldLabel(field: string): string {
  return (
    {
      operation_date: "Дата операции",
      posting_date: "Дата проводки",
      description: "Описание",
      amount: "Сумма",
      debit_amount: "Списание",
      credit_amount: "Зачисление",
      currency: "Валюта",
      balance_after: "Остаток",
    }[field] ?? field
  );
}
