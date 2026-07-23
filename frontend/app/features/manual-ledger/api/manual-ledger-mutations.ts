import type { components } from "../../../api/generated/schema";
import {
  parseApiError,
  requestJson,
  type ApiTransportResult,
} from "../../../api/transport";
import {
  manualOperationSchema,
  type ManualOperationDto,
} from "./manual-ledger-api";

export type ManualOperationCreateRequest =
  | components["schemas"]["ManualIncomeExpenseCreateApiRequest"]
  | components["schemas"]["ManualTransferCreateApiRequest"];
export type ManualOperationUpdateRequest =
  | components["schemas"]["ManualIncomeExpenseUpdateApiRequest"]
  | components["schemas"]["ManualTransferUpdateApiRequest"];
export type ManualOperationLifecycleAction = "cancel" | "restore";

export type ManualLedgerMutationResult =
  | { status: "success"; operation: ManualOperationDto }
  | { status: "unauthenticated" }
  | {
      status: "validation_error";
      message: string;
      fieldErrors: Record<string, string[]>;
    }
  | { status: "conflict"; message: string }
  | { status: "error"; message: string };

export type ManualOperationDeleteResult =
  | { status: "success" }
  | { status: "unauthenticated" }
  | { status: "conflict" | "error"; message: string };

export async function createManualOperation(
  request: ManualOperationCreateRequest,
  csrfToken: string,
  idempotencyKey: string,
): Promise<ManualLedgerMutationResult> {
  const response = await requestJson("/api/v1/manual-ledger", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Idempotency-Key": idempotencyKey,
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(request),
  });
  return manualOperationResult(
    response,
    "API вернул созданную операцию неожиданного формата.",
  );
}

export async function updateManualOperation(
  operationId: string,
  request: ManualOperationUpdateRequest,
  csrfToken: string,
): Promise<ManualLedgerMutationResult> {
  const response = await requestJson(`/api/v1/manual-ledger/${operationId}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify(request),
  });
  return manualOperationResult(
    response,
    "API вернул обновлённую операцию неожиданного формата.",
  );
}

export async function changeManualOperationLifecycle(
  operationId: string,
  action: ManualOperationLifecycleAction,
  version: number,
  csrfToken: string,
): Promise<ManualLedgerMutationResult> {
  const response = await requestJson(
    `/api/v1/manual-ledger/${operationId}/${action}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({ version }),
    },
  );
  return manualOperationResult(
    response,
    "API вернул операцию неожиданного формата.",
  );
}

export async function deleteManualOperation(
  operationId: string,
  version: number,
  csrfToken: string,
): Promise<ManualOperationDeleteResult> {
  const response = await requestJson(`/api/v1/manual-ledger/${operationId}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    body: JSON.stringify({ version }),
  });
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) {
    return { status: "unauthenticated" };
  }
  if (response.httpStatus === 204) {
    return { status: "success" };
  }
  const apiError = parseApiError(response.body);
  if (apiError === null) {
    return {
      status: "error",
      message: `API вернул статус ${response.httpStatus}.`,
    };
  }
  return {
    status: response.httpStatus === 409 ? "conflict" : "error",
    message: apiError.message,
  };
}

function manualOperationResult(
  response: ApiTransportResult,
  invalidResponseMessage: string,
): ManualLedgerMutationResult {
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) {
    return { status: "unauthenticated" };
  }
  if (response.ok) {
    const operation = manualOperationSchema.safeParse(response.body);
    return operation.success
      ? { status: "success", operation: operation.data }
      : { status: "error", message: invalidResponseMessage };
  }
  const apiError = parseApiError(response.body);
  if (apiError === null) {
    return {
      status: "error",
      message: `API вернул статус ${response.httpStatus}.`,
    };
  }
  if (response.httpStatus === 422) {
    return {
      status: "validation_error",
      message: apiError.message,
      fieldErrors: createFieldErrors(apiError.fieldErrors),
    };
  }
  if (response.httpStatus === 409) {
    return { status: "conflict", message: apiError.message };
  }
  return { status: "error", message: apiError.message };
}

function createFieldErrors(
  errors: Record<string, string[]>,
): Record<string, string[]> {
  return Object.fromEntries(
    Object.entries(errors).map(([field, messages]) => [
      field.split(".").at(-1) ?? field,
      messages,
    ]),
  );
}
