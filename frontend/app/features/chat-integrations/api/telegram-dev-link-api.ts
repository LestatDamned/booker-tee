import { z } from "zod";

import {
  apiLoadError,
  apiLoadNetworkError,
  apiMutationError,
  apiMutationNetworkError,
  apiUnauthenticatedFailure,
  apiUnexpectedStatusError,
  type ApiLoadError,
  type ApiMutationError,
  type ApiUnauthenticatedFailure,
} from "../../../api/failures";
import type { components } from "../../../api/generated/schema";
import { parseApiError, requestJson } from "../../../api/transport";

type TelegramDevLinkConfigDto =
  components["schemas"]["TelegramDevLinkConfigApiResponse"];

const configSchema: z.ZodType<TelegramDevLinkConfigDto> = z.object({
  enabled: z.literal(true),
});

const bindSchema = z.object({ bound: z.literal(true) });

export type TelegramDevLinkConfigResult =
  | { status: "success" }
  | ApiUnauthenticatedFailure
  | { status: "not_found" }
  | ApiLoadError;

export type BindTelegramDevLinkResult =
  | { status: "success" }
  | ApiUnauthenticatedFailure
  | { status: "not_found" }
  | ApiMutationError;

export async function loadTelegramDevLinkConfig(
  signal?: AbortSignal,
): Promise<TelegramDevLinkConfigResult> {
  const response = await requestJson(
    "/api/v1/chat-integrations/telegram/dev-link",
    signal ? { signal } : undefined,
  );
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (response.httpStatus === 404) return { status: "not_found" };
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = configSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success" }
    : apiLoadError("API вернул конфигурацию неожиданного формата.");
}

export async function bindTelegramDevLink({
  csrfToken,
  displayName,
  externalUserId,
}: {
  csrfToken: string;
  displayName: string;
  externalUserId: string;
}): Promise<BindTelegramDevLinkResult> {
  const response = await requestJson(
    "/api/v1/chat-integrations/telegram/dev-link",
    {
      body: JSON.stringify({
        externalUserId,
        displayName: displayName || null,
      }),
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      method: "POST",
    },
  );
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (response.httpStatus === 404) return { status: "not_found" };
  const error = parseApiError(response.body);
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "telegram_dev_link_failed",
      fallbackMessage: "Не удалось привязать Telegram аккаунт.",
    });
  }
  const parsed = bindSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success" }
    : apiMutationError(null, {
        fallbackCode: "invalid_telegram_dev_link_response",
        fallbackMessage: "API вернул неожиданный результат привязки.",
      });
}
