import { describe, expect, it } from "vitest";

import { directory } from "./test-support";
import {
  categoryListQuery,
  categoryListUrl,
  categoryMatchesSearch,
  categoryMatchesView,
} from "./category-list-query";

const kindLabels = new Map(
  directory.kindOptions.map((option) => [option.value, option.label]),
);

describe("category list query", () => {
  it("normalizes invalid and historical all views to active", () => {
    expect(
      categoryListQuery("?view=all&search=%20%20еда%20%20дома%20"),
    ).toEqual({
      view: "active",
      search: "еда дома",
    });
    expect(categoryListQuery("?view=system").view).toBe("system");
    expect(categoryListQuery("?view=archived").view).toBe("archived");
  });

  it("keeps applied search while switching views", () => {
    expect(categoryListUrl("system", "  без   категории ")).toBe(
      "?view=system&search=%D0%B1%D0%B5%D0%B7+%D0%BA%D0%B0%D1%82%D0%B5%D0%B3%D0%BE%D1%80%D0%B8%D0%B8",
    );
    expect(categoryListUrl("active", "")).toBe(".");
  });

  it("matches lifecycle views and localized kind or notes", () => {
    const active = directory.items[0]!;
    const archived = directory.items[2]!;
    const system = directory.items[3]!;

    expect(categoryMatchesView(active, "active")).toBe(true);
    expect(categoryMatchesView(archived, "archived")).toBe(true);
    expect(categoryMatchesView(system, "system")).toBe(true);
    expect(categoryMatchesSearch(active, "расход", kindLabels)).toBe(true);
    expect(categoryMatchesSearch(active, "доставка", kindLabels)).toBe(true);
    expect(categoryMatchesSearch(active, "зарплата", kindLabels)).toBe(false);
  });
});
