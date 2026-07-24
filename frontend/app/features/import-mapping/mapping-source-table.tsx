import type {
  ImportMappingCommand,
  ImportMappingSourceTable,
} from "./api/import-mapping-api";
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
  errors,
  onChange,
  table,
}: {
  command: ImportMappingCommand;
  disabled: boolean;
  errors: MappingFieldErrors;
  onChange: (command: ImportMappingCommand) => void;
  table: ImportMappingSourceTable;
}) {
  const amountMode = mappingAmountMode(command);
  const options = mappingRoleOptions(amountMode);
  const missingErrors = Object.entries(errors).filter(
    ([field]) =>
      mappingColumnRoles.includes(field as MappingColumnRole) &&
      !mappingColumnRoles.some(
        (role) => role === field && command[role] != null,
      ),
  );

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
          <summary>
            Почему роли заполнены так
            {table.suggestion.confidence != null
              ? ` · ${Math.round(table.suggestion.confidence * 100)}%`
              : ""}
          </summary>
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
            {table.sampleRows.map((row) => (
              <tr
                data-start={
                  row.rowNumber === command.firstDataRowNumber || undefined
                }
                key={row.rowNumber}
              >
                <th scope="row">{row.rowNumber}</th>
                {Array.from({ length: table.columnCount }, (_, columnIndex) => (
                  <td key={columnIndex}>
                    {row.cells[columnIndex] || (
                      <span className={styles.emptyCell}>—</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.rowCount > table.sampleRows.length ? (
        <p className={styles.boundedNote}>
          Показано {table.sampleRows.length} из {table.rowCount} исходных строк.
          Итоговый предпросмотр рассчитывается сервером по всему документу.
        </p>
      ) : null}
    </section>
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
