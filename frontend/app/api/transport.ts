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

type ApiRequestOptions = Omit<RequestInit, "headers"> & {
  headers?: Record<string, string>;
};

export async function requestJson(
  input: RequestInfo | URL,
  options: ApiRequestOptions = {},
): Promise<ApiTransportResult> {
  try {
    const response = await fetch(input, {
      credentials: "same-origin",
      ...options,
      headers: {
        Accept: "application/json",
        ...options.headers,
      },
    });
    return {
      status: "response",
      body: await readJsonBody(response),
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
