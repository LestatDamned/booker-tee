import { z } from "zod";

import type { components } from "../../../api/generated/schema";
import { requestJson } from "../../../api/transport";

export type ReportOverviewDto =
  components["schemas"]["ReportOverviewApiResponse"];

const namedOptionSchema = z.object({
  id: z.uuid(),
  name: z.string(),
  isActive: z.boolean(),
});

const decimalStringSchema = z.string().regex(/^[+-]?\d+(?:\.\d+)?$/);

const moneySummarySchema = z.object({
  currency: z.string().length(3),
  income: decimalStringSchema,
  expense: decimalStringSchema,
  profit: decimalStringSchema,
});

export const reportOverviewSchema: z.ZodType<ReportOverviewDto> = z.object({
  workspaceName: z.string(),
  appliedFilters: z.object({
    dateFrom: z.iso.date().nullable(),
    dateTo: z.iso.date().nullable(),
    currency: z.string().length(3),
    accountId: z.uuid().nullable(),
    categoryId: z.uuid().nullable(),
    propertyId: z.uuid().nullable(),
  }),
  filterOptions: z.object({
    accounts: z.array(
      namedOptionSchema.extend({ currency: z.string().length(3) }),
    ),
    categories: z.array(namedOptionSchema),
    properties: z.array(namedOptionSchema),
    currencies: z.array(z.string().length(3)),
  }),
  summary: moneySummarySchema,
  accountBalances: z.array(
    z.object({
      accountId: z.uuid(),
      name: z.string(),
      currency: z.string().length(3),
      balance: decimalStringSchema,
      isActive: z.boolean(),
    }),
  ),
  categoryRows: z.array(
    moneySummarySchema.extend({
      categoryId: z.uuid().nullable(),
      name: z.string(),
      isActive: z.boolean(),
    }),
  ),
  propertyRows: z.array(
    moneySummarySchema.extend({
      propertyId: z.uuid(),
      name: z.string(),
      isActive: z.boolean(),
    }),
  ),
  balanceAsOf: z.iso.date().nullable(),
  nextReviewDocumentId: z.uuid().nullable(),
});

export type ReportOverviewLoadResult =
  | { status: "success"; overview: ReportOverviewDto }
  | { status: "unauthenticated" }
  | { status: "error"; message: string };

const reportApiParameters = [
  "date_from",
  "date_to",
  "currency",
  "account_id",
  "category_id",
  "property_id",
] as const;

export async function loadReportOverview(
  search: string,
  signal?: AbortSignal,
): Promise<ReportOverviewLoadResult> {
  const input = new URLSearchParams(search);
  const query = new URLSearchParams();
  for (const key of reportApiParameters) {
    const value = input.get(key);
    if (value) query.set(key, value);
  }
  const response = await requestJson(
    `/api/v1/reports${query.size > 0 ? `?${query.toString()}` : ""}`,
    signal ? { signal } : {},
  );
  if (response.status === "network_error") {
    return { status: "error", message: "Backend недоступен." };
  }
  if (response.httpStatus === 401) return { status: "unauthenticated" };
  if (!response.ok) {
    return {
      status: "error",
      message:
        response.httpStatus === 400
          ? "Проверьте период и выбранные фильтры."
          : `API вернул статус ${response.httpStatus}.`,
    };
  }
  const parsed = reportOverviewSchema.safeParse(response.body);
  if (!parsed.success) {
    return {
      status: "error",
      message: "API вернул отчёт неожиданного формата.",
    };
  }
  return { status: "success", overview: parsed.data };
}
