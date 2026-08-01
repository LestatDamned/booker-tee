import { describe, expect, it } from "vitest";

import {
  categoryDetailApiSearch,
  categoryDetailPageSizeUrl,
  categoryDetailPageUrl,
  categoryDetailSearchUrl,
  safeReportsReturnPath,
} from "./category-detail-query";

describe("category detail query", () => {
  it("keeps return_to local to React reports and out of the API", () => {
    expect(
      safeReportsReturnPath(
        "/app/reports?date_from=2026-07-01&currency=RUB#categories",
      ),
    ).toBe("/app/reports?date_from=2026-07-01&currency=RUB#categories");
    expect(safeReportsReturnPath("https://evil.test/app/reports")).toBeNull();
    expect(safeReportsReturnPath("/app/accounts")).toBeNull();
    expect(
      categoryDetailApiSearch(
        "?currency=RUB&return_to=%2Fapp%2Freports%3Fcurrency%3DRUB",
      ),
    ).toBe("?currency=RUB");
  });

  it("changes only operation pagination", () => {
    expect(
      categoryDetailPageUrl(
        "/categories/id",
        "?currency=RUB&return_to=%2Fapp%2Freports",
        2,
      ),
    ).toBe(
      "/categories/id?currency=RUB&return_to=%2Fapp%2Freports&operations_page=2",
    );
  });

  it("preserves financial and return context while changing collection controls", () => {
    const current =
      "?currency=RUB&type=expense&operations_page=3&return_to=%2Fapp%2Freports";

    expect(
      categoryDetailSearchUrl("/categories/id", current, "  market  "),
    ).toBe(
      "/categories/id?currency=RUB&type=expense&return_to=%2Fapp%2Freports&search=market",
    );
    expect(categoryDetailPageSizeUrl("/categories/id", current, 50)).toBe(
      "/categories/id?currency=RUB&type=expense&return_to=%2Fapp%2Freports&operations_page_size=50",
    );
  });
});
