import { z } from "zod";

import type { components } from "../../api/generated/schema";
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
const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    fieldErrors: z.record(z.string(), z.array(z.string())).nullish(),
  }),
});

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
  try {
    const response = await fetch("/api/v1/manual-ledger", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(request),
    });
    if (response.status === 401) {
      return { status: "unauthenticated" };
    }

    const responseBody: unknown = await response.json();
    if (response.ok) {
      const operation = manualOperationSchema.safeParse(responseBody);
      return operation.success
        ? { status: "success", operation: operation.data }
        : {
            status: "error",
            message: "API вернул созданную операцию неожиданного формата.",
          };
    }

    const apiError = apiErrorSchema.safeParse(responseBody);
    if (!apiError.success) {
      return {
        status: "error",
        message: `API вернул статус ${response.status}.`,
      };
    }
    if (response.status === 422) {
      return {
        status: "validation_error",
        message: apiError.data.error.message,
        fieldErrors: createFieldErrors(apiError.data.error.fieldErrors ?? {}),
      };
    }
    if (response.status === 409) {
      return { status: "conflict", message: apiError.data.error.message };
    }
    return { status: "error", message: apiError.data.error.message };
  } catch {
    return { status: "error", message: "Backend недоступен." };
  }
}

export async function updateManualOperation(
  operationId: string,
  request: ManualOperationUpdateRequest,
  csrfToken: string,
): Promise<ManualLedgerMutationResult> {
  try {
    const response = await fetch(`/api/v1/manual-ledger/${operationId}`, {
      method: "PUT",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(request),
    });
    if (response.status === 401) {
      return { status: "unauthenticated" };
    }

    const responseBody: unknown = await response.json();
    if (response.ok) {
      const operation = manualOperationSchema.safeParse(responseBody);
      return operation.success
        ? { status: "success", operation: operation.data }
        : {
            status: "error",
            message: "API вернул обновлённую операцию неожиданного формата.",
          };
    }

    const apiError = apiErrorSchema.safeParse(responseBody);
    if (!apiError.success) {
      return {
        status: "error",
        message: `API вернул статус ${response.status}.`,
      };
    }
    if (response.status === 422) {
      return {
        status: "validation_error",
        message: apiError.data.error.message,
        fieldErrors: createFieldErrors(apiError.data.error.fieldErrors ?? {}),
      };
    }
    if (response.status === 409) {
      return { status: "conflict", message: apiError.data.error.message };
    }
    return { status: "error", message: apiError.data.error.message };
  } catch {
    return { status: "error", message: "Backend недоступен." };
  }
}

export async function changeManualOperationLifecycle(
  operationId: string,
  action: ManualOperationLifecycleAction,
  version: number,
  csrfToken: string,
): Promise<ManualLedgerMutationResult> {
  try {
    const response = await fetch(
      `/api/v1/manual-ledger/${operationId}/${action}`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ version }),
      },
    );
    if (response.status === 401) {
      return { status: "unauthenticated" };
    }

    const responseBody: unknown = await response.json();
    if (response.ok) {
      const operation = manualOperationSchema.safeParse(responseBody);
      return operation.success
        ? { status: "success", operation: operation.data }
        : {
            status: "error",
            message: "API вернул операцию неожиданного формата.",
          };
    }

    const apiError = apiErrorSchema.safeParse(responseBody);
    if (!apiError.success) {
      return {
        status: "error",
        message: `API вернул статус ${response.status}.`,
      };
    }
    if (response.status === 409) {
      return { status: "conflict", message: apiError.data.error.message };
    }
    return { status: "error", message: apiError.data.error.message };
  } catch {
    return { status: "error", message: "Backend недоступен." };
  }
}

export async function deleteManualOperation(
  operationId: string,
  version: number,
  csrfToken: string,
): Promise<ManualOperationDeleteResult> {
  try {
    const response = await fetch(`/api/v1/manual-ledger/${operationId}`, {
      method: "DELETE",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({ version }),
    });
    if (response.status === 401) {
      return { status: "unauthenticated" };
    }
    if (response.status === 204) {
      await response.arrayBuffer();
      return { status: "success" };
    }

    const responseBody: unknown = await response.json();
    const apiError = apiErrorSchema.safeParse(responseBody);
    if (!apiError.success) {
      return {
        status: "error",
        message: `API вернул статус ${response.status}.`,
      };
    }
    return {
      status: response.status === 409 ? "conflict" : "error",
      message: apiError.data.error.message,
    };
  } catch {
    return { status: "error", message: "Backend недоступен." };
  }
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
