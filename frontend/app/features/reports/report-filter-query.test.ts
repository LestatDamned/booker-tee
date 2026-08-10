import { describe, expect, it } from "vitest";

import { reportOverview } from "./test-support";
import {
  reportAllTimeSearch,
  reportCategorySort,
  reportCategorySortDirection,
  reportCategorySortSearch,
  reportCurrentMonthRange,
  reportCurrentMonthSearch,
  reportFilterSearch,
  reportMonthlyExportHref,
  reportMonthSearch,
} from "./report-filter-query";

describe("report filter query", () => {
  it("applies filters, preserves presentation sorting and removes incompatible pagination", () => {
    const search = reportFilterSearch(
      {
        dateFrom: "2026-06-01",
        dateTo: "2026-06-30",
        currency: "USD",
        accountId: "",
        categoryId: "",
        propertyId: "",
      },
      "?category_sort=expense&uncategorized_page=4",
    );

    expect(search).toContain("date_from=2026-06-01");
    expect(search).toContain("currency=USD");
    expect(search).toContain("category_sort=expense");
    expect(search).not.toContain("uncategorized_page");
  });

  it("normalizes category sorting and keeps the default URL compact", () => {
    expect(reportCategorySort("?category_sort=income")).toBe("income");
    expect(reportCategorySort("?category_sort=unknown")).toBe("turnover");
    expect(reportCategorySortDirection("?category_sort=result")).toBe("desc");
    expect(
      reportCategorySortDirection(
        "?category_sort=result&category_sort_dir=asc",
      ),
    ).toBe("asc");
    expect(reportCategorySortSearch("?currency=RUB", "result")).toContain(
      "category_sort=result",
    );
    expect(
      reportCategorySortSearch("?currency=RUB&category_sort=result", "result"),
    ).toContain("category_sort_dir=asc");
    expect(
      reportCategorySortSearch(
        "?currency=RUB&category_sort=expense&category_sort_dir=asc",
        "turnover",
      ),
    ).toBe("?currency=RUB");
  });

  it("moves months while preserving explicit currency", () => {
    expect(reportMonthSearch(reportOverview, -1, "?currency=RUB")).toContain(
      "date_from=2026-06-01",
    );
    expect(reportMonthSearch(reportOverview, -1, "?currency=RUB")).toContain(
      "date_to=2026-06-30",
    );
  });

  it("builds the current month from the local calendar date", () => {
    const now = new Date(2026, 7, 1, 0, 30);
    expect(reportCurrentMonthRange(now)).toEqual({
      dateFrom: "2026-08-01",
      dateTo: "2026-08-31",
    });
    const search = reportCurrentMonthSearch(
      reportOverview,
      "?currency=RUB",
      now,
    );
    expect(search).toContain("date_from=2026-08-01");
    expect(search).toContain("date_to=2026-08-31");
  });

  it("clears only the period for all-time view", () => {
    const search = reportAllTimeSearch(
      {
        ...reportOverview,
        appliedFilters: {
          ...reportOverview.appliedFilters,
          accountId,
        },
      },
      "?date_from=2026-07-01&date_to=2026-07-31",
    );
    expect(search).not.toContain("date_from");
    expect(search).toContain(`account_id=${accountId}`);
  });

  it("builds a bounded export URL only for a full calendar month", () => {
    expect(reportMonthlyExportHref(reportOverview)).toBe(
      "/api/v1/reports/export.xlsx?month=2026-07&currency=RUB",
    );
    expect(
      reportMonthlyExportHref({
        ...reportOverview,
        appliedFilters: {
          ...reportOverview.appliedFilters,
          dateTo: "2026-07-30",
        },
      }),
    ).toBeNull();
  });

  it("drops superseded presentation state and resets bounded pages", () => {
    const filtered = reportFilterSearch(
      {
        dateFrom: "2026-07-01",
        dateTo: "2026-07-31",
        currency: "RUB",
        accountId: "",
        categoryId: "",
        propertyId: "",
      },
      "?breakdown=properties&metric=income&uncategorized_page=8&uncategorized_page_size=10",
    );
    expect(filtered).not.toContain("uncategorized_page=8");
    expect(filtered).toContain("uncategorized_page_size=10");
    expect(filtered).not.toContain("breakdown");
    expect(filtered).not.toContain("metric");
  });
});

const accountId = "4958dd80-af47-4131-8f16-16c0ca04f63c";
