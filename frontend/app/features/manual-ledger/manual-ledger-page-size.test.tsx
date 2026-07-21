import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import { ManualLedgerPageSize } from "./manual-ledger-page-size";

describe("ManualLedgerPageSize", () => {
  it("preserves filters and resets pagination when density changes", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter
        initialEntries={["/ledger/manual?type=expense&page=3&per_page=50"]}
      >
        <ManualLedgerPageSize options={[25, 50, 100]} value={50} />
        <LocationProbe />
      </MemoryRouter>,
    );

    await user.selectOptions(screen.getByLabelText("На странице"), "100");

    expect(screen.getByTestId("location-search")).toHaveTextContent(
      "type=expense&page=1&per_page=100",
    );
  });
});

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location-search">{location.search}</output>;
}
