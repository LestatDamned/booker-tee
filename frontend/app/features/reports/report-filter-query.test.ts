import { describe, expect, it } from "vitest";

import { reportOverview } from "./test-support";
import {
  reportAllTimeSearch,
  reportCategorySort,
  reportCategorySortSearch,
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

  it("uses name ascending by default and numeric descending on first selection", () => {
    expect(reportCategorySort("")).toEqual({
      field: "name",
      direction: "asc",
    });
    expect(reportCategorySortSearch("?currency=RUB", "expense")).toBe(
      "?currency=RUB&category_sort=expense&category_sort_dir=desc",
    );
    expect(
      reportCategorySort("?category_sort=unknown&category_sort_dir=desc"),
    ).toEqual({ field: "name", direction: "asc" });
  });

  it("toggles the active sort and preserves it across period navigation", () => {
    const toggled = reportCategorySortSearch(
      "?category_sort=profit&category_sort_dir=desc&currency=RUB",
      "profit",
    );
    expect(reportCategorySort(toggled)).toEqual({
      field: "profit",
      direction: "asc",
    });

    const moved = reportMonthSearch(reportOverview, -1, toggled);
    expect(reportCategorySort(moved)).toEqual({
      field: "profit",
      direction: "asc",
    });
  });

  it.each([
    ["name", "?category_sort=profit&category_sort_dir=desc", "asc"],
    ["income", "", "desc"],
    ["expense", "", "desc"],
    ["profit", "", "desc"],
  ] as const)(
    "selects %s with its expected initial direction",
    (field, currentSearch, direction) => {
      expect(
        reportCategorySort(reportCategorySortSearch(currentSearch, field)),
      ).toEqual({ field, direction });
    },
  );
});

const accountId = "4958dd80-af47-4131-8f16-16c0ca04f63c";
