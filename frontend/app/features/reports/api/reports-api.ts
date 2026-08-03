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
  balanceSummary: z.object({
    currency: z.string().length(3),
    openingBalance: decimalStringSchema,
    closingBalance: decimalStringSchema,
    balanceChange: decimalStringSchema,
  }),
  accountBalances: z.array(
    z.object({
      accountId: z.uuid(),
      name: z.string(),
      currency: z.string().length(3),
      openingBalance: decimalStringSchema,
      closingBalance: decimalStringSchema,
      balanceChange: decimalStringSchema,
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
  uncategorized: z.object({
    items: z.array(
      z.object({
        operationId: z.uuid(),
        version: z.number().int().positive(),
        operationDate: z.iso.date(),
        operationType: z.enum(["income", "expense", "transfer", "adjustment"]),
        description: z.string(),
        source: z.enum(["manual", "bank_pdf", "system"]),
        signedAmount: decimalStringSchema,
        currency: z.string().length(3),
        accountId: z.uuid().nullable(),
        capabilities: z.object({
          canCorrect: z.boolean(),
          readonlyReasonCode: z
            .enum([
              "financial_write_forbidden",
              "system_operation",
              "correction_account_unavailable",
            ])
            .nullable(),
        }),
      }),
    ),
    page: z.number().int().positive(),
    pageSize: z.number().int().positive().max(25),
    total: z.number().int().nonnegative(),
    totalPages: z.number().int().positive(),
    hasPrevious: z.boolean(),
    hasNext: z.boolean(),
  }),
});

export type ReportOverviewLoadResult =
  | { status: "success"; overview: ReportOverviewDto }
  | ApiUnauthenticatedFailure
  | ApiLoadError;

const reportApiParameters = [
  "date_from",
  "date_to",
  "currency",
  "account_id",
  "category_id",
  "property_id",
  "uncategorized_page",
  "uncategorized_page_size",
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
    return apiLoadNetworkError();
  }
  if (response.httpStatus === 401) return apiUnauthenticatedFailure();
  if (!response.ok) {
    return response.httpStatus === 400
      ? apiLoadError("Проверьте период и выбранные фильтры.")
      : apiUnexpectedStatusError(response.httpStatus);
  }
  const parsed = reportOverviewSchema.safeParse(response.body);
  if (!parsed.success) {
    return apiLoadError("API вернул отчёт неожиданного формата.");
  }
  return { status: "success", overview: parsed.data };
}
