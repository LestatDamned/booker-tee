import type { components } from "../../api/generated/schema";
import { parseApiError, requestBlob, requestJson } from "../../api/transport";

export type CoordinateOverview =
  components["schemas"]["CoordinateMappingOverview"];
export type CoordinateSpec = components["schemas"]["CoordinateMappingSpec"];
export type CoordinateControlRegion =
  components["schemas"]["CoordinateControlRegion"];
export type CoordinatePreview = components["schemas"]["CoordinatePreview"];
export type CoordinateImport =
  components["schemas"]["CoordinateImportApiResponse"];
export type CoordinatePageImageResult =
  | { status: "success"; value: Blob }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

type Result<T> =
  | { status: "success"; value: T }
  | { status: "unauthenticated" | "forbidden" | "not_found" }
  | { status: "error"; message: string };

export async function loadCoordinateOverview(
  documentId: string,
  signal?: AbortSignal,
): Promise<Result<CoordinateOverview>> {
  const response = await requestJson(
    `/api/v1/imports/documents/${documentId}/coordinate-mapping`,
    signal ? { signal } : {},
  );
  return parseResult<CoordinateOverview>(response);
}

export async function previewCoordinates(
  documentId: string,
  spec: CoordinateSpec,
  controlRegions: CoordinateControlRegion[],
  csrfToken: string,
): Promise<Result<CoordinatePreview>> {
  const response = await requestJson(
    `/api/v1/imports/documents/${documentId}/coordinate-mapping/preview`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({ spec, controlRegions }),
    },
  );
  return parseResult<CoordinatePreview>(response);
}

export async function importCoordinates(
  documentId: string,
  spec: CoordinateSpec,
  controlRegions: CoordinateControlRegion[],
  templateName: string | null,
  csrfToken: string,
  idempotencyKey: string,
): Promise<Result<CoordinateImport>> {
  const response = await requestJson(
    `/api/v1/imports/documents/${documentId}/coordinate-mapping/import`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify({ spec, controlRegions, templateName }),
    },
  );
  return parseResult<CoordinateImport>(response);
}

export async function loadCoordinatePageImage(
  documentId: string,
  pageNumber: number,
  signal?: AbortSignal,
): Promise<CoordinatePageImageResult> {
  const response = await requestBlob(
    `/api/v1/imports/documents/${documentId}/coordinate-mapping/pages/${pageNumber}/image`,
    signal,
  );
  if (response.status === "network_error")
    return { status: "error", message: "Нет соединения с сервером." };
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (response.ok && response.blob)
    return { status: "success", value: response.blob };
  return { status: "error", message: "Не удалось загрузить страницу PDF." };
}

function parseResult<T>(
  response: Awaited<ReturnType<typeof requestJson>>,
): Result<T> {
  if (response.status === "network_error")
    return { status: "error", message: "Нет соединения с сервером." };
  if (response.ok && response.body && typeof response.body === "object")
    return { status: "success", value: response.body as T };
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (response.httpStatus === 403) return { status: "forbidden" };
  if (response.httpStatus === 404) return { status: "not_found" };
  return {
    status: "error",
    message:
      parseApiError(response.body)?.message ?? "Не удалось выполнить запрос.",
  };
}
