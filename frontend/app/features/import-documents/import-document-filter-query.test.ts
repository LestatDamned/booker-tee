import { describe, expect, it } from "vitest";

import {
  importDocumentAdvancedFilterCount,
  importDocumentFilterDraft,
  importDocumentFilterSearch,
  importDocumentFiltersAreActive,
  importDocumentPageUrl,
  importDocumentPaginationItems,
  importDocumentPaginationRangeLabel,
  importDocumentStateUrl,
} from "./import-document-filter-query";

const filterOptions = {
  accounts: [
    {
      id: "4958dd80-af47-4131-8f16-16c0ca04f63c",
      name: "Основной",
      currency: "RUB",
      bankName: "Альфа-Банк",
    },
  ],
  perPage: [25, 50, 100],
};

describe("import document filter query", () => {
  it("hydrates only supported account and date values", () => {
    expect(
      importDocumentFilterDraft(
        "?account_id=unknown&period_from=not-a-date&period_to=2026-07-31&sort=created_at_asc",
        filterOptions,
      ),
    ).toEqual({
      accountId: "",
      periodFrom: "",
      periodTo: "2026-07-31",
      sort: "created_at_asc",
    });
  });

  it("applies advanced filters while preserving state and resetting the page", () => {
    const result = importDocumentFilterSearch(
      {
        accountId: filterOptions.accounts[0]!.id,
        periodFrom: "2026-07-01",
        periodTo: "2026-07-31",
        sort: "created_at_asc",
      },
      "?state=attention&page=8&per_page=50",
    );

    expect(new URLSearchParams(result)).toEqual(
      new URLSearchParams(
        `state=attention&page=1&per_page=50&account_id=${filterOptions.accounts[0]!.id}&period_from=2026-07-01&period_to=2026-07-31&sort=created_at_asc`,
      ),
    );
  });

  it("preserves filters across state and page navigation", () => {
    expect(
      importDocumentStateUrl(
        "?account_id=account-1&page=4&per_page=50",
        "completed",
      ),
    ).toBe("?account_id=account-1&page=1&per_page=50&state=completed");
    expect(
      importDocumentPageUrl("?state=completed&account_id=account-1", 3),
    ).toBe("?state=completed&account_id=account-1&page=3");
  });

  it("counts filter categories and recognizes active quick filters", () => {
    const search =
      "?state=attention&account_id=account-1&period_from=2026-07-01&period_to=2026-07-31";

    expect(importDocumentFiltersAreActive(search)).toBe(true);
    expect(importDocumentAdvancedFilterCount(search)).toBe(2);
    expect(importDocumentFiltersAreActive("?sort=created_at_asc")).toBe(false);
  });

  it("builds compact pagination and human-readable ranges", () => {
    expect(importDocumentPaginationItems(1, 1)).toEqual([1]);
    expect(importDocumentPaginationItems(5, 10)).toEqual([
      1,
      "ellipsis-1",
      4,
      5,
      6,
      "ellipsis-6",
      10,
    ]);
    expect(importDocumentPaginationRangeLabel(3, 25, 63)).toBe("51–63 из 63");
    expect(importDocumentPaginationRangeLabel(1, 25, 0)).toBe("0 документов");
  });
});
