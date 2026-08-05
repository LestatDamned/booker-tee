import { z } from "zod";

import {
  apiLoadError,
  apiLoadNetworkError,
  apiUnauthenticatedFailure,
  apiUnexpectedStatusError,
  type ApiLoadError,
  type ApiUnauthenticatedFailure,
} from "../../../api/failures";
import type { components } from "../../../api/generated/schema";
import { requestJson } from "../../../api/transport";

export type DashboardOverviewDto =
  components["schemas"]["DashboardOverviewApiResponse"];
export type DashboardDocumentDto =
  components["schemas"]["DashboardDocumentApiResponse"];

const documentStatusSchema = z.enum([
  "uploaded",
  "pending_parse",
  "parsing",
  "parsed",
  "requires_review",
  "failed_to_parse",
  "imported",
  "ignored",
]);

const dashboardDocumentSchema: z.ZodType<DashboardDocumentDto> = z.object({
  id: z.uuid(),
  filename: z.string(),
  status: documentStatusSchema,
  createdAt: z.iso.datetime({ offset: true }),
  account: z
    .object({
      id: z.uuid(),
      name: z.string(),
      currency: z.string(),
    })
    .nullable(),
  reviewableRowCount: z.number().int().nonnegative(),
  nextStepKind: z.enum(["detail", "mapping", "review"]),
});

export const dashboardOverviewSchema: z.ZodType<DashboardOverviewDto> =
  z.object({
    workspaceName: z.string(),
    period: z.object({ start: z.iso.date(), end: z.iso.date() }),
    summary: z.object({
      currency: z.string(),
      income: z.string(),
      expense: z.string(),
      profit: z.string(),
    }),
    accounts: z.array(
      z.object({
        id: z.uuid(),
        name: z.string(),
        currency: z.string(),
        balance: z.string(),
      }),
    ),
    activeAccountCount: z.number().int().nonnegative(),
    attention: z.object({
      total: z.number().int().nonnegative(),
      items: z.array(dashboardDocumentSchema),
    }),
    recentDocuments: z.array(dashboardDocumentSchema),
    onboarding: z.object({
      hasAccounts: z.boolean(),
      hasDocuments: z.boolean(),
      hasConfirmedActivity: z.boolean(),
      isComplete: z.boolean(),
    }),
    capabilities: z.object({
      canUpload: z.boolean(),
      canWriteFinancialData: z.boolean(),
      primaryAction: z.enum(["upload", "manual_operation", "reports"]),
    }),
  });

export type DashboardLoadResult =
  | { status: "success"; dashboard: DashboardOverviewDto }
  | ApiUnauthenticatedFailure
  | ApiLoadError;

export async function loadDashboard(
  signal?: AbortSignal,
): Promise<DashboardLoadResult> {
  const response = await requestJson("/api/v1/dashboard", {
    ...(signal ? { signal } : {}),
  });
  if (response.status === "network_error") return apiLoadNetworkError();
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (!response.ok) return apiUnexpectedStatusError(response.httpStatus);
  const parsed = dashboardOverviewSchema.safeParse(response.body);
  if (!parsed.success) {
    return apiLoadError("API вернул обзор неожиданного формата.");
  }
  return { status: "success", dashboard: parsed.data };
}
