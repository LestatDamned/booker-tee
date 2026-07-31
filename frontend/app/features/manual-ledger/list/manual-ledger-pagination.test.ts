import { describe, expect, it } from "vitest";

import {
  manualLedgerPaginationRangeLabel,
  manualLedgerPageUrl,
} from "./manual-ledger-pagination";

describe("manual ledger pagination", () => {
  it("preserves filters when changing the page", () => {
    expect(manualLedgerPageUrl("?type=expense&page=1", 2)).toBe(
      "?type=expense&page=2",
    );
  });

  it("describes the visible range", () => {
    expect(manualLedgerPaginationRangeLabel(2, 25, 61)).toBe("26–50 из 61");
    expect(manualLedgerPaginationRangeLabel(1, 25, 0)).toBe("0 операций");
  });
});
