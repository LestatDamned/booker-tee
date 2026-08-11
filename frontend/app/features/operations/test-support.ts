import type { OperationDto, OperationsDto } from "./api/operations-api";

export function operationsFixture(): OperationsDto {
  const items: OperationDto[] = [
    operationFixture("manual", "Ручной расход"),
    operationFixture("bank_pdf", "Импортированный расход"),
    operationFixture("debt", "Платёж по долгу"),
    operationFixture("system", "Системная корректировка"),
  ];
  return {
    items,
    pagination: {
      page: 1,
      perPage: 50,
      total: items.length,
      totalPages: 1,
      hasPrevious: false,
      hasNext: false,
    },
    filterOptions: {
      accounts: [
        {
          id: crypto.randomUUID(),
          name: "Основной счёт",
          currency: "RUB",
          canRecordIncome: true,
          canRecordExpense: true,
          canTransfer: true,
        },
      ],
      categories: [],
      properties: [],
      sources: ["manual", "bank_pdf", "debt", "system"],
      perPage: [25, 50, 100, 200],
    },
    capabilities: { canCreate: true, readonlyReason: null },
    targetOperationId: null,
    targetOperation: null,
  };
}

export function operationFixture(
  source: OperationDto["source"],
  description: string,
): OperationDto {
  const imported = source === "bank_pdf";
  return {
    id: crypto.randomUUID(),
    version: 1,
    operationType: "expense",
    source,
    status: "confirmed",
    operationDate: "2026-08-11",
    description,
    money: { amount: "100.00", currency: "RUB" },
    account: {
      id: crypto.randomUUID(),
      name: "Основной счёт",
      currency: "RUB",
    },
    sourceAccount: null,
    destinationAccount: null,
    category: null,
    property: null,
    provenance: imported
      ? {
          kind: "import",
          uploadedDocumentId: crypto.randomUUID(),
          rawTransactionId: crypto.randomUUID(),
        }
      : source === "debt"
        ? { kind: "debt", debtAccountId: crypto.randomUUID() }
        : source === "system"
          ? { kind: "system" }
          : null,
    capabilities: imported
      ? {
          canEdit: true,
          editKind: "imported",
          canCancel: false,
          canRestore: false,
          canDelete: false,
          readonlyReason: null,
        }
      : source === "manual"
        ? {
            canEdit: true,
            editKind: "manual",
            canCancel: true,
            canRestore: false,
            canDelete: false,
            readonlyReason: null,
          }
        : {
            canEdit: false,
            editKind: "none",
            canCancel: false,
            canRestore: false,
            canDelete: false,
            readonlyReason:
              source === "system"
                ? "system_operation"
                : "source_workflow_required",
          },
  };
}
