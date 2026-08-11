import { describe, expect, it } from "vitest";

import { clientLoader } from "./manual-ledger";

describe("manual ledger compatibility route", () => {
  it("redirects to operations and preserves the complete query", async () => {
    const response = await clientLoader({
      request: new Request(
        "http://localhost/app/ledger/manual?type=expense&page=2&layout=flat",
      ),
    } as never);

    expect(response).toBeInstanceOf(Response);
    expect(response.status).toBe(302);
    expect(response.headers.get("Location")).toBe(
      "/operations?type=expense&page=2&layout=flat",
    );
  });
});
