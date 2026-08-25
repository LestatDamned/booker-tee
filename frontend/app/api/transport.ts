import { z } from "zod";

const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    fieldErrors: z.record(z.string(), z.array(z.string())).nullish(),
    details: z.record(z.string(), z.unknown()).nullish(),
  }),
});

export type ApiErrorDetails = {
  code: string;
  fieldErrors: Record<string, string[]>;
  message: string;
  details?: Record<string, unknown>;
};

export type ApiTransportResult =
  | {
      status: "response";
      body: unknown;
      httpStatus: number;
      ok: boolean;
    }
  | { status: "network_error" };

export type ApiBlobResult =
  | { status: "response"; blob: Blob | null; httpStatus: number; ok: boolean }
  | { status: "network_error" };

type ApiRequestOptions = Omit<RequestInit, "headers"> & {
  auth?: boolean;
  headers?: Record<string, string>;
};

let accessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export async function restoreAccessToken(): Promise<boolean> {
  return Boolean(await refreshAccessToken());
}

export async function requestJson(
  input: RequestInfo | URL,
  options: ApiRequestOptions = {},
): Promise<ApiTransportResult> {
  const { auth = true, ...requestOptions } = options;
  try {
    if (auth && !accessToken && refreshPromise) {
      await refreshPromise;
    }
    const sentAccessToken = accessToken;
    let response = await fetch(input, {
      credentials: "same-origin",
      ...requestOptions,
      headers: {
        Accept: "application/json",
        ...(auth && accessToken
          ? { Authorization: `Bearer ${accessToken}` }
          : {}),
        ...options.headers,
      },
    });
    if (auth && sentAccessToken && response.status === 401) {
      accessToken = null;
      if (await refreshAccessToken()) {
        response = await fetch(input, {
          credentials: "same-origin",
          ...requestOptions,
          headers: {
            Accept: "application/json",
            Authorization: `Bearer ${accessToken}`,
            ...options.headers,
          },
        });
      }
    }
    const body = await readJsonBody(response);
    rememberAccessToken(body);
    return {
      status: "response",
      body,
      httpStatus: response.status,
      ok: response.ok,
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    return { status: "network_error" };
  }
}

export async function requestBlob(
  input: RequestInfo | URL,
  signal?: AbortSignal,
): Promise<ApiBlobResult> {
  try {
    if (!accessToken && refreshPromise) {
      await refreshPromise;
    }
    const sentAccessToken = accessToken;
    let response = await fetch(input, {
      credentials: "same-origin",
      ...(signal ? { signal } : {}),
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });
    if (sentAccessToken && response.status === 401) {
      accessToken = null;
      if (await refreshAccessToken()) {
        response = await fetch(input, {
          credentials: "same-origin",
          ...(signal ? { signal } : {}),
          headers: { Authorization: `Bearer ${accessToken}` },
        });
      }
    }
    return {
      status: "response",
      blob: response.ok ? await response.blob() : null,
      httpStatus: response.status,
      ok: response.ok,
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    return { status: "network_error" };
  }
}

async function refreshAccessToken(): Promise<string | null> {
  refreshPromise ??= performRefresh().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

async function performRefresh(retryRace = true): Promise<string | null> {
  const response = await fetch("/api/v1/auth/refresh", {
    method: "POST",
    credentials: "same-origin",
    headers: { Accept: "application/json" },
  });
  if (response.status === 409 && retryRace) {
    await new Promise((resolve) => setTimeout(resolve, 50));
    return performRefresh(false);
  }
  if (!response.ok) {
    accessToken = null;
    return null;
  }
  const body = await readJsonBody(response);
  rememberAccessToken(body);
  return accessToken;
}

function rememberAccessToken(body: unknown): void {
  if (
    typeof body === "object" &&
    body !== null &&
    "accessToken" in body &&
    typeof body.accessToken === "string"
  ) {
    accessToken = body.accessToken;
  }
}

export function parseApiError(body: unknown): ApiErrorDetails | null {
  const parsed = apiErrorSchema.safeParse(body);
  if (!parsed.success) {
    return null;
  }
  return {
    code: parsed.data.error.code,
    fieldErrors: parsed.data.error.fieldErrors ?? {},
    message: parsed.data.error.message,
    ...(parsed.data.error.details
      ? { details: parsed.data.error.details }
      : {}),
  };
}

async function readJsonBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}
