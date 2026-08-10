import type { SessionDto } from "../../api/session";
import type {
  ImportMappingCommand,
  ImportMappingDto,
  ImportMappingPreviewDto,
} from "./api/import-mapping-api";

export const mappingDocumentId = "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8";

export const mappingSession: SessionDto = {
  user: {
    id: "f4835818-f111-41d6-a59d-62f541ace357",
    email: "max@example.test",
    name: "Max",
  },
  workspace: {
    id: "c12c9ac8-6851-4467-b87a-da7fc70586c8",
    name: "Дом",
    type: "personal",
    defaultCurrency: "RUB",
  },
  membership: { role: "owner", status: "active" },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: true,
    canManageImports: true,
    canViewRawImportData: true,
    canViewMemberDirectory: true,
    canManageMembers: true,
    canViewWorkspaceActivity: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};

export function importMappingPayload(): ImportMappingDto {
  const defaultMapping: ImportMappingCommand = {
    tableRef: { pageNumber: 1, tableIndex: 0 },
    operationDateColumn: 0,
    postingDateColumn: null,
    descriptionColumn: 1,
    amountColumn: 2,
    debitAmountColumn: null,
    creditAmountColumn: null,
    currencyColumn: null,
    balanceAfterColumn: 3,
    firstDataRowNumber: 2,
    defaultCurrency: "RUB",
    unsignedAmountDirection: "require_sign",
    openingBalanceCell: null,
    closingBalanceCell: null,
  };
  return {
    documentId: mappingDocumentId,
    filename: "statement-with-unknown-columns.pdf",
    status: "requires_review",
    bankName: "Неизвестный банк",
    statementType: null,
    account: {
      id: "4958dd80-af47-4131-8f16-16c0ca04f63c",
      name: "Основной счёт",
      currency: "RUB",
    },
    defaultCurrency: "RUB",
    capability: { allowed: true, blockingReasonCodes: [] },
    defaultMapping,
    defaultSource: "analyzer",
    selectedTemplateId: null,
    templates: [],
    tables: [
      {
        ref: { pageNumber: 1, tableIndex: 0 },
        sourceType: "table",
        rowCount: 3,
        columnCount: 4,
        isContinuation: false,
        sampleRows: [
          {
            rowNumber: 1,
            cells: ["Дата", "Назначение платежа", "Сумма", "Остаток"],
          },
          {
            rowNumber: 2,
            cells: [
              "20.07.2026",
              "Оплата продуктов в магазине",
              "-1250,50",
              "10000,00",
            ],
          },
          {
            rowNumber: 3,
            cells: ["21.07.2026", "Зачисление", "50000,00", "60000,00"],
          },
        ],
        candidates: [
          {
            field: "operation_date",
            columnIndex: 0,
            header: "Дата",
          },
          {
            field: "description",
            columnIndex: 1,
            header: "Назначение платежа",
          },
          {
            field: "amount",
            columnIndex: 2,
            header: "Сумма",
          },
        ],
        suggestion: {
          mapping: defaultMapping,
          reasons: [
            {
              field: "operation_date",
              columnIndex: 0,
              header: "Дата",
              evidence: "date_values",
              matchedCount: 2,
              sampleCount: 2,
            },
          ],
          warningCodes: [],
        },
      },
      {
        ref: { pageNumber: 2, tableIndex: 0 },
        sourceType: "table",
        rowCount: 2,
        columnCount: 4,
        isContinuation: true,
        sampleRows: [
          {
            rowNumber: 1,
            cells: ["Операция", "Текст", "Расход", "Приход"],
          },
          {
            rowNumber: 2,
            cells: ["22.07.2026", "Оплата связи", "700,00", ""],
          },
        ],
        candidates: [],
        suggestion: {
          mapping: {
            ...defaultMapping,
            tableRef: { pageNumber: 2, tableIndex: 0 },
            amountColumn: null,
            debitAmountColumn: 2,
            creditAmountColumn: 3,
            balanceAfterColumn: null,
          },
          reasons: [],
          warningCodes: [],
        },
      },
    ],
    controlTotalCandidates: [],
    totalTableCount: 2,
    tablesTruncated: false,
  };
}

export function importMappingPreview(): ImportMappingPreviewDto {
  return {
    rows: [
      {
        tableRef: { pageNumber: 1, tableIndex: 0 },
        sourceRowNumber: 2,
        operationDate: "2026-07-20",
        operationDateRaw: "20.07.2026",
        postingDate: null,
        postingDateRaw: "",
        description:
          "Списание средств по длинному назначению платежа, которое важно показать полностью",
        amount: "-1250.50",
        amountRaw: "-1250,50",
        currency: "RUB",
        balanceAfter: "10000.00",
        balanceAfterRaw: "10000,00",
        status: "valid",
        errorCodes: [],
      },
    ],
    totalRowCount: 2,
    validRowCount: 2,
    invalidRowCount: 0,
    rowLimit: 10,
    rowsTruncated: true,
    compatibleTables: [{ pageNumber: 1, tableIndex: 0 }],
    warnings: [],
    controlTotals: [],
    reconciliation: null,
    canImport: true,
  };
}
