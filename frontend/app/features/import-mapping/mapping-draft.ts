import type {
  ImportMappingCommand,
  ImportMappingSourceTable,
} from "./api/import-mapping-api";

export type MappingFieldErrors = Record<string, string>;
export type AmountMode = "single" | "split";
export type MappingColumnRole =
  | "operationDateColumn"
  | "postingDateColumn"
  | "descriptionColumn"
  | "amountColumn"
  | "debitAmountColumn"
  | "creditAmountColumn"
  | "currencyColumn"
  | "balanceAfterColumn";

export const mappingColumnRoles: MappingColumnRole[] = [
  "operationDateColumn",
  "postingDateColumn",
  "descriptionColumn",
  "amountColumn",
  "debitAmountColumn",
  "creditAmountColumn",
  "currencyColumn",
  "balanceAfterColumn",
];

export function mappingTableKey(
  tableRef: ImportMappingCommand["tableRef"],
): string {
  return `${tableRef.pageNumber}:${tableRef.tableIndex}`;
}

export function mappingForTable(
  table: ImportMappingSourceTable,
  fallback: ImportMappingCommand,
): ImportMappingCommand {
  if (table.suggestion) {
    return {
      ...table.suggestion.mapping,
      defaultCurrency: fallback.defaultCurrency,
      openingBalanceCell: fallback.openingBalanceCell ?? null,
      closingBalanceCell: fallback.closingBalanceCell ?? null,
    };
  }
  return {
    ...fallback,
    tableRef: table.ref,
    firstDataRowNumber: Math.min(
      Math.max(fallback.firstDataRowNumber, 1),
      Math.max(table.rowCount, 1),
    ),
  };
}

export function mappingFingerprint(command: ImportMappingCommand): string {
  return JSON.stringify(command);
}

export function mappingAmountMode(command: ImportMappingCommand): AmountMode {
  return command.amountColumn != null ? "single" : "split";
}

export function mappingRoleForColumn(
  command: ImportMappingCommand,
  columnIndex: number,
): MappingColumnRole | null {
  return (
    mappingColumnRoles.find((role) => command[role] === columnIndex) ?? null
  );
}

export function mappingRoleCanBeAssigned(
  command: ImportMappingCommand,
  columnIndex: number,
  role: MappingColumnRole,
): boolean {
  const currentRole = mappingRoleForColumn(command, columnIndex);
  return (
    currentRole == null ||
    !isRequiredMappingRole(currentRole, mappingAmountMode(command)) ||
    command[role] != null
  );
}

export function assignMappingColumnRole(
  command: ImportMappingCommand,
  columnIndex: number,
  nextRole: MappingColumnRole | null,
): ImportMappingCommand {
  const currentRole = mappingRoleForColumn(command, columnIndex);
  if (currentRole === nextRole) return command;
  if (nextRole == null) {
    if (
      currentRole == null ||
      isRequiredMappingRole(currentRole, mappingAmountMode(command))
    ) {
      return command;
    }
    return setMappingRole(command, currentRole, null);
  }

  const previousColumn = command[nextRole];
  if (
    currentRole &&
    previousColumn == null &&
    isRequiredMappingRole(currentRole, mappingAmountMode(command))
  ) {
    return command;
  }

  let next = command;
  if (currentRole) {
    next = setMappingRole(next, currentRole, previousColumn ?? null);
  }
  return setMappingRole(next, nextRole, columnIndex);
}

export function isRequiredMappingRole(
  role: MappingColumnRole,
  amountMode: AmountMode,
): boolean {
  return (
    role === "operationDateColumn" ||
    role === "descriptionColumn" ||
    (amountMode === "single"
      ? role === "amountColumn"
      : role === "debitAmountColumn" || role === "creditAmountColumn")
  );
}

export function suggestedColumn(
  table: ImportMappingSourceTable,
  field: string,
): number | null {
  return (
    table.candidates.find((candidate) => candidate.field === field)
      ?.columnIndex ?? null
  );
}

export function mappingColumnOptions(
  table: ImportMappingSourceTable,
  command: ImportMappingCommand,
): Array<{ label: string; value: number }> {
  const headerRow =
    table.sampleRows.find(
      (row) => row.rowNumber === command.firstDataRowNumber - 1,
    ) ?? table.sampleRows[0];
  return Array.from({ length: table.columnCount }, (_, index) => {
    const candidateHeader = table.candidates.find(
      (candidate) => candidate.columnIndex === index && candidate.header.trim(),
    )?.header;
    const rawHeader = headerRow?.cells[index]?.trim();
    return {
      value: index,
      label: `${index + 1} · ${candidateHeader || rawHeader || `Колонка ${index + 1}`}`,
    };
  });
}

export function validateMappingDraft(
  command: ImportMappingCommand,
  table: ImportMappingSourceTable,
): MappingFieldErrors {
  const errors: MappingFieldErrors = {};
  if (command.operationDateColumn >= table.columnCount) {
    errors.operationDateColumn = "Выберите колонку с датой операции.";
  }
  if (command.descriptionColumn >= table.columnCount) {
    errors.descriptionColumn = "Выберите колонку с описанием.";
  }
  if (
    command.firstDataRowNumber < 1 ||
    command.firstDataRowNumber > table.rowCount
  ) {
    errors.firstDataRowNumber = `Укажите строку от 1 до ${Math.max(table.rowCount, 1)}.`;
  }
  const selected = selectedColumns(command);
  const duplicates = duplicateFields(selected);
  for (const field of duplicates) {
    errors[field] = "Эта колонка уже используется для другой роли.";
  }
  if (mappingAmountMode(command) === "single") {
    if (command.amountColumn == null) {
      errors.amountColumn = "Выберите колонку с суммой.";
    }
  } else {
    if (command.debitAmountColumn == null) {
      errors.debitAmountColumn = "Выберите колонку списания.";
    }
    if (command.creditAmountColumn == null) {
      errors.creditAmountColumn = "Выберите колонку зачисления.";
    }
  }
  if (!/^[A-Z]{3}$/u.test(command.defaultCurrency)) {
    errors.defaultCurrency = "Используйте трёхбуквенный код, например RUB.";
  }
  return errors;
}

function selectedColumns(
  command: ImportMappingCommand,
): Array<[string, number]> {
  const fields: Array<[string, number | null | undefined]> = [
    ["operationDateColumn", command.operationDateColumn],
    ["postingDateColumn", command.postingDateColumn],
    ["descriptionColumn", command.descriptionColumn],
    ["amountColumn", command.amountColumn],
    ["debitAmountColumn", command.debitAmountColumn],
    ["creditAmountColumn", command.creditAmountColumn],
    ["currencyColumn", command.currencyColumn],
    ["balanceAfterColumn", command.balanceAfterColumn],
  ];
  return fields.filter((field): field is [string, number] => field[1] != null);
}

function duplicateFields(fields: Array<[string, number]>): string[] {
  const byColumn = new Map<number, string[]>();
  for (const [field, column] of fields) {
    byColumn.set(column, [...(byColumn.get(column) ?? []), field]);
  }
  return [...byColumn.values()].filter((group) => group.length > 1).flat();
}

function setMappingRole(
  command: ImportMappingCommand,
  role: MappingColumnRole,
  columnIndex: number | null,
): ImportMappingCommand {
  if (
    (role === "operationDateColumn" || role === "descriptionColumn") &&
    columnIndex == null
  ) {
    return command;
  }
  return { ...command, [role]: columnIndex };
}
