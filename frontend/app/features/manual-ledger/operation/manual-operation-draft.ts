import type { components } from "../../../api/generated/schema";
import type { ManualOperationDto } from "../api/manual-ledger-api";
import type {
  ManualOperationCreateRequest,
  ManualOperationUpdateRequest,
} from "../api/manual-ledger-mutations";

export type ManualOperationType =
  | components["schemas"]["ManualIncomeExpenseCreateApiRequest"]["operationType"]
  | components["schemas"]["ManualTransferCreateApiRequest"]["operationType"];

export type ManualOperationDraft = {
  accountId: string;
  amount: string;
  categoryId: string;
  description: string;
  destinationAccountId: string;
  operationDate: string;
  operationType: ManualOperationType | "";
  propertyId: string;
};

export function emptyManualOperationDraft(): ManualOperationDraft {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return {
    accountId: "",
    amount: "",
    categoryId: "",
    description: "",
    destinationAccountId: "",
    operationDate: `${year}-${month}-${day}`,
    operationType: "",
    propertyId: "",
  };
}

export function editDraftFromOperation(
  operation: ManualOperationDto,
): ManualOperationDraft | null {
  const operationType = operation.operationType;
  if (!operation.money || operationType === "adjustment") {
    return null;
  }
  return {
    accountId:
      operationType === "transfer"
        ? (operation.sourceAccount?.id ?? "")
        : (operation.account?.id ?? ""),
    amount: operation.money.amount,
    categoryId: operation.category?.id ?? "",
    description: operation.description,
    destinationAccountId: operation.destinationAccount?.id ?? "",
    operationDate: operation.operationDate,
    operationType,
    propertyId: operation.property?.id ?? "",
  };
}

export function operationTypeLabel(
  value: ManualOperationDraft["operationType"],
): string {
  if (value === "expense") {
    return "расход";
  }
  if (value === "transfer") {
    return "перевод";
  }
  return value === "income" ? "доход" : "операцию";
}

export function manualOperationCreateRequest(
  draft: ManualOperationDraft,
): ManualOperationCreateRequest {
  return manualOperationRequest(draft);
}

export function manualOperationUpdateRequest(
  draft: ManualOperationDraft,
  version: number,
): ManualOperationUpdateRequest {
  return { ...manualOperationRequest(draft), version };
}

function manualOperationRequest(
  draft: ManualOperationDraft,
): ManualOperationCreateRequest {
  const common = {
    amount: draft.amount,
    operationDate: draft.operationDate,
    description: draft.description,
  };
  if (draft.operationType === "") {
    throw new Error("Operation type is required before request mapping.");
  }
  if (draft.operationType === "transfer") {
    return {
      ...common,
      operationType: "transfer",
      sourceAccountId: draft.accountId,
      destinationAccountId: draft.destinationAccountId,
    };
  }
  return {
    ...common,
    operationType: draft.operationType,
    accountId: draft.accountId,
    categoryId: draft.categoryId || null,
    propertyId: draft.propertyId || null,
  };
}
