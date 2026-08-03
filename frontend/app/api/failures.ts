import type { ApiErrorDetails } from "./transport";

export type ApiUnauthenticatedFailure = { status: "unauthenticated" };
export type ApiForbiddenFailure = { status: "forbidden"; message: string };
export type ApiLoadError = { status: "error"; message: string };
export type ApiMutationError = { status: "error" } & ApiErrorDetails;

export function apiUnauthenticatedFailure(): ApiUnauthenticatedFailure {
  return { status: "unauthenticated" };
}

export function apiForbiddenFailure(
  error: ApiErrorDetails | null,
  fallbackMessage: string,
): ApiForbiddenFailure {
  return { status: "forbidden", message: error?.message ?? fallbackMessage };
}

export function apiLoadError(message: string): ApiLoadError {
  return { status: "error", message };
}

export function apiLoadNetworkError(): ApiLoadError {
  return apiLoadError("Backend недоступен.");
}

export function apiUnexpectedStatusError(httpStatus: number): ApiLoadError {
  return apiLoadError(`API вернул статус ${httpStatus}.`);
}

export function apiResponseErrorMessage(
  error: ApiErrorDetails | null,
  httpStatus: number,
): string {
  return error?.message ?? `API вернул статус ${httpStatus}.`;
}

export function apiMutationNetworkError(): ApiMutationError {
  return apiMutationError(null, {
    fallbackCode: "network_error",
    fallbackMessage: "Backend недоступен. Проверьте соединение и повторите.",
  });
}

export function apiMutationError(
  error: ApiErrorDetails | null,
  {
    fallbackCode,
    fallbackMessage,
  }: { fallbackCode: string; fallbackMessage: string },
): ApiMutationError {
  return {
    status: "error",
    code: error?.code ?? fallbackCode,
    ...(error?.details ? { details: error.details } : {}),
    fieldErrors: error?.fieldErrors ?? {},
    message: error?.message ?? fallbackMessage,
  };
}
