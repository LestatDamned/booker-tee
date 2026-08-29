import { z } from "zod";

import {
  apiMutationError,
  apiMutationNetworkError,
  apiUnauthenticatedFailure,
  type ApiMutationError,
  type ApiUnauthenticatedFailure,
} from "../../../api/failures";
import { parseApiError, requestJson } from "../../../api/transport";

const linkCodeSchema = z.object({
  command: z.string().min(1),
  expiresAt: z.iso.datetime({ offset: true }),
});

export type TelegramLinkCode = z.infer<typeof linkCodeSchema>;

export type IssueTelegramLinkCodeResult =
  | { status: "success"; linkCode: TelegramLinkCode }
  | ApiUnauthenticatedFailure
  | ApiMutationError;

export async function issueTelegramLinkCode(
  csrfToken: string,
): Promise<IssueTelegramLinkCodeResult> {
  const response = await requestJson(
    "/api/v1/chat-integrations/telegram/link-code",
    {
      headers: { "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
  if (response.status === "network_error") return apiMutationNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  const error = parseApiError(response.body);
  if (!response.ok) {
    return apiMutationError(error, {
      fallbackCode: "telegram_link_code_failed",
      fallbackMessage: "Не удалось создать код привязки.",
    });
  }
  const parsed = linkCodeSchema.safeParse(response.body);
  return parsed.success
    ? { status: "success", linkCode: parsed.data }
    : apiMutationError(null, {
        fallbackCode: "invalid_telegram_link_code_response",
        fallbackMessage: "API вернул неожиданный результат.",
      });
}
