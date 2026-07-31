import { describe, expect, it } from "vitest";

import { reportOverview } from "./test-support";
import {
  reportAllTimeSearch,
  reportFilterSearch,
  reportMonthSearch,
} from "./report-filter-query";

describe("report filter query", () => {
  it("applies filters and removes incompatible pagination", () => {
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

  it("moves months while preserving explicit currency", () => {
    expect(reportMonthSearch(reportOverview, -1, "?currency=RUB")).toContain(
      "date_from=2026-06-01",
    );
    expect(reportMonthSearch(reportOverview, -1, "?currency=RUB")).toContain(
      "date_to=2026-06-30",
    );
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
});

const accountId = "4958dd80-af47-4131-8f16-16c0ca04f63c";
