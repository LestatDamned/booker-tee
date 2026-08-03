import { describe, expect, it } from "vitest";

import { formatIsoDate, todayIsoDate } from "./format-date";

describe("formatIsoDate", () => {
  it("formats an API date without applying a timezone", () => {
    expect(formatIsoDate("2026-07-20")).toBe("20.07.2026");
  });

  it("rejects a value outside the API date contract", () => {
    expect(() => formatIsoDate("20.07.2026")).toThrow(RangeError);
  });
});

describe("todayIsoDate", () => {
  it("uses the user's local calendar date", () => {
    expect(todayIsoDate(new Date(2026, 7, 1, 0, 30))).toBe("2026-08-01");
  });

  it("pads local month and day values", () => {
    expect(todayIsoDate(new Date(2026, 0, 5, 23, 30))).toBe("2026-01-05");
  });
});
