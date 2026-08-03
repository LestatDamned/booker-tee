import { describe, expect, it, vi } from "vitest";

import {
  loginHref,
  loginHrefForLocation,
  redirectIfUnauthenticated,
} from "./unauthenticated";

describe("unauthenticated session navigation", () => {
  it("builds an encoded login URL for an explicit destination", () => {
    expect(loginHref("/app/accounts?status=active")).toBe(
      "/login?next=%2Fapp%2Faccounts%3Fstatus%3Dactive",
    );
  });

  it("preserves the complete browser location in the login return URL", () => {
    expect(
      loginHrefForLocation({
        pathname: "/app/rules",
        search: "?page=2&status=active",
        hash: "#rule-7",
      }),
    ).toBe("/login?next=%2Fapp%2Frules%3Fpage%3D2%26status%3Dactive%23rule-7");
  });

  it("redirects only unauthenticated results", () => {
    const assign = vi.fn();
    const location = {
      assign,
      hash: "#operation-3",
      pathname: "/app/ledger/manual",
      search: "?type=expense&page=2",
    };

    expect(redirectIfUnauthenticated({ status: "forbidden" }, location)).toBe(
      false,
    );
    expect(assign).not.toHaveBeenCalled();

    expect(
      redirectIfUnauthenticated({ status: "unauthenticated" }, location),
    ).toBe(true);
    expect(assign).toHaveBeenCalledWith(
      "/login?next=%2Fapp%2Fledger%2Fmanual%3Ftype%3Dexpense%26page%3D2%23operation-3",
    );
  });
});
