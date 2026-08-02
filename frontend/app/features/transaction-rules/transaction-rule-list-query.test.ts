import { describe, expect, it } from "vitest";

import {
  transactionRuleApiSearch,
  transactionRuleListQuery,
  transactionRulePageUrl,
  transactionRuleSearchUrl,
  transactionRuleStatusUrl,
} from "./transaction-rule-list-query";
import { categoryId } from "./test-support";

describe("transaction rule URL state", () => {
  it("normalizes invalid values into a deterministic API query", () => {
    expect(
      transactionRuleApiSearch(
        "?status=archived&page=-2&page_size=500&category_id=foreign&q=%20%20ozon%20%20travel%20",
      ),
    ).toBe("?q=ozon+travel");
  });

  it("preserves valid search, category and page size", () => {
    const query = transactionRuleListQuery(
      `?q=ozon&category_id=${categoryId}&status=disabled&page=2&page_size=25`,
    );
    expect(query).toEqual({
      q: "ozon",
      categoryId,
      status: "disabled",
      page: 2,
      pageSize: 25,
    });
  });

  it("resets page when search or status changes and preserves it for pagination", () => {
    const current = "?q=ozon&status=active&page=3&page_size=25";
    expect(transactionRuleSearchUrl(current, " travel ")).toBe(
      "?q=travel&status=active&page_size=25",
    );
    expect(transactionRuleStatusUrl(current, "disabled")).toBe(
      "?q=ozon&status=disabled&page_size=25",
    );
    expect(transactionRulePageUrl(current, 4)).toBe(
      "?q=ozon&status=active&page=4&page_size=25",
    );
  });
});
