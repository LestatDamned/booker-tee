import { describe, expect, it } from "vitest";

import { accountDetailApiSearch } from "./account-detail-loader";

describe("account detail loader", () => {
  it("keeps financial filters out of frontend-only return context", () => {
    const search = accountDetailApiSearch(
      "?date_from=2026-07-01&status=confirmed&return_to=%2Fapp%2Freports%3Fcurrency%3DRUB",
    );

    expect(search).toContain("date_from=2026-07-01");
    expect(search).toContain("status=confirmed");
    expect(search).not.toContain("return_to");
  });
});
