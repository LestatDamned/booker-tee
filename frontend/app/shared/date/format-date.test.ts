import { describe, expect, it } from "vitest";

import { formatIsoDate } from "./format-date";

describe("formatIsoDate", () => {
  it("formats an API date without applying a timezone", () => {
    expect(formatIsoDate("2026-07-20")).toBe("20.07.2026");
  });

  it("rejects a value outside the API date contract", () => {
    expect(() => formatIsoDate("20.07.2026")).toThrow(RangeError);
  });
});
