import { z } from "zod";

import {
  apiForbiddenFailure,
  apiLoadError,
  apiLoadNetworkError,
  apiMutationError,
  apiMutationNetworkError,
  apiUnauthenticatedFailure,
  apiUnexpectedStatusError,
  type ApiForbiddenFailure,
  type ApiLoadError,
  type ApiMutationError,
  type ApiUnauthenticatedFailure,
} from "../../../api/failures";
import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";

export type AccountDirectoryDto =
  components["schemas"]["AccountDirectoryApiResponse"];
export type AccountSummaryDto =
  components["schemas"]["AccountSummaryApiResponse"];
export type AccountType = components["schemas"]["AccountType"];

const accountTypeSchema = z.enum([
  "cash",
  "card",
  "deposit",
  "checking",
  "other",
]);

export const accountSummarySchema: z.ZodType<AccountSummaryDto> = z.object({
  id: z.uuid(),
  name: z.string(),
  accountType: accountTypeSchema,
  currency: z.string(),
  initialBalance: z.string(),
  balance: z.string(),
  balanceDirection: z.enum(["positive", "negative", "zero"]),
  movementCount: z.number().int().nonnegative(),
  isActive: z.boolean(),
  updatedAt: z.iso.datetime({ offset: true }),
  capabilities: z.object({
    canArchive: z.boolean(),
    canRestore: z.boolean(),
  }),
});

export const accountDirectorySchema: z.ZodType<AccountDirectoryDto> = z.object({
  items: z.array(accountSummarySchema),
  accountTypes: z.array(accountTypeSchema),
  capabilities: z.object({
    canCreate: z.boolean(),
    readonlyReasonCode: z.enum(["financial_write_forbidden"]).nullable(),
  }),
});

export type AccountDirectoryLoadResult =
  | { status: "success"; directory: AccountDirectoryDto }
  | ApiUnauthenticatedFailure
  | ApiLoadError;

export type CreateAccountDraft = {
  accountType: AccountType;
  currency: string;
  initialBalance: string;
  name: string;
};

export type CreateAccountResult =
  | { status: "success"; account: AccountSummaryDto }
  | ApiUnauthenticatedFailure
  | ApiForbiddenFailure
  | ApiMutationError;

export type AccountLifecycleAction = "archive" | "restore";
export type AccountMutationSnapshot = Pick<
  AccountSummaryDto,
  "id" | "isActive" | "updatedAt"
>;
export type UpdateAccountDraft = CreateAccountDraft & {
  expectedUpdatedAt: string;
};

export type AccountLifecycleResult =
  | { status: "success"; account: AccountSummaryDto }
  | ApiUnauthenticatedFailure
  | ApiForbiddenFailure
  | { status: "conflict"; message: string }
  | ApiMutationError;

export type UpdateAccountResult =
  | { status: "success"; account: AccountSummaryDto }
  | ApiUnauthenticatedFailure
  | ApiForbiddenFailure
  | { status: "conflict"; code: string; message: string }
  | ApiMutationError;

export async function loadAccounts(
  signal?: AbortSignal,
): Promise<AccountDirectoryLoadResult> {
  const response = await requestJson("/api/v1/accounts", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") {
    return apiLoadNetworkError();
  }
  if (response.httpStatus === 401) {
    return apiUnauthenticatedFailure();
  }
  if (!response.ok) {
    return apiUnexpectedStatusError(response.httpStatus);
  }
  const parsed = accountDirectorySchema.safeParse(response.body);
  if (!parsed.success) {
    return apiLoadError("API вернул список счетов неожиданного формата.");
  }
  return { status: "success", directory: parsed.data };
}

export async function createAccount({
  csrfToken,
  draft,
}: {
  csrfToken: string;
  draft: CreateAccountDraft;
}): Promise<CreateAccountResult> {
  const response = await requestJson("/api/v1/accounts", {
    body: JSON.stringify(draft),
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    method: "POST",
  });
  if (response.status === "network_error") {
    return apiMutationNetworkError();
  }
  if (response.httpStatus === 401) {
    return apiUnauthenticatedFailure();
  }
  const apiError = parseApiError(response.body);
  if (response.httpStatus === 403) {
    return apiForbiddenFailure(apiError, "Создание счета недоступно.");
  }
  if (!response.ok) {
    return apiMutationError(apiError, {
      fallbackCode: "account_create_failed",
      fallbackMessage: "Не удалось создать счёт.",
    });
  }
  const parsed = accountSummarySchema.safeParse(response.body);
  if (!parsed.success) {
    return apiMutationError(null, {
      fallbackCode: "invalid_account_response",
      fallbackMessage: "API вернул созданный счёт неожиданного формата.",
    });
  }
  return { status: "success", account: parsed.data };
}

export async function changeAccountLifecycle({
  account,
  action,
  csrfToken,
}: {
  account: AccountMutationSnapshot;
  action: AccountLifecycleAction;
  csrfToken: string;
}): Promise<AccountLifecycleResult> {
  const response = await requestJson(
    `/api/v1/accounts/${account.id}/${action}`,
    {
      body: JSON.stringify({
        expectedActive: account.isActive,
        expectedUpdatedAt: account.updatedAt,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      method: "POST",
    },
  );
  if (response.status === "network_error") {
    return apiMutationNetworkError();
  }
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const apiError = parseApiError(response.body);
  if (response.httpStatus === 403) {
    return apiForbiddenFailure(apiError, "Изменение счета недоступно.");
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      message: apiError?.message ?? "Счёт уже изменился. Обновите список.",
    };
  }
  if (!response.ok) {
    return apiMutationError(apiError, {
      fallbackCode: "account_lifecycle_failed",
      fallbackMessage: "Не удалось изменить состояние счёта.",
    });
  }
  const parsed = accountSummarySchema.safeParse(response.body);
  if (!parsed.success) {
    return apiMutationError(null, {
      fallbackCode: "invalid_account_response",
      fallbackMessage: "API вернул счёт неожиданного формата.",
    });
  }
  return { status: "success", account: parsed.data };
}

export async function updateAccount({
  accountId,
  csrfToken,
  draft,
}: {
  accountId: string;
  csrfToken: string;
  draft: UpdateAccountDraft;
}): Promise<UpdateAccountResult> {
  const response = await requestJson(`/api/v1/accounts/${accountId}`, {
    body: JSON.stringify(draft),
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": csrfToken,
    },
    method: "PUT",
  });
  if (response.status === "network_error") {
    return apiMutationNetworkError();
  }
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const apiError = parseApiError(response.body);
  if (response.httpStatus === 403) {
    return apiForbiddenFailure(apiError, "Изменение счёта недоступно.");
  }
  if (response.httpStatus === 409) {
    return {
      status: "conflict",
      code: apiError?.code ?? "account_update_conflict",
      message: apiError?.message ?? "Счёт уже изменился.",
    };
  }
  if (!response.ok) {
    return apiMutationError(apiError, {
      fallbackCode: "account_update_failed",
      fallbackMessage: "Не удалось сохранить изменения.",
    });
  }
  const parsed = accountSummarySchema.safeParse(response.body);
  if (!parsed.success) {
    return apiMutationError(null, {
      fallbackCode: "invalid_account_response",
      fallbackMessage: "API вернул счёт неожиданного формата.",
    });
  }
  return { status: "success", account: parsed.data };
}
