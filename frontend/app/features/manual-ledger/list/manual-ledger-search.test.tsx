import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import { ManualLedgerSearch } from "./manual-ledger-search";

describe("manual ledger search", () => {
  it("preserves filters, normalizes the query and resets page state", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter
        initialEntries={[
          "/operations?type=expense&page=3&per_page=25&operation_id=target",
        ]}
      >
        <ManualLedgerSearch />
        <LocationProbe />
      </MemoryRouter>,
    );

    await user.type(
      screen.getByLabelText("Поиск по описанию"),
      "  аренда   июль  ",
    );
    await user.click(screen.getByRole("button", { name: "Найти" }));

    expect(screen.getByTestId("location-search")).toHaveTextContent(
      "type=expense&page=1&per_page=25&search=%D0%B0%D1%80%D0%B5%D0%BD%D0%B4%D0%B0+%D0%B8%D1%8E%D0%BB%D1%8C",
    );
    expect(screen.getByTestId("location-search")).not.toHaveTextContent(
      "operation_id",
    );
  });
});

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location-search">{location.search}</output>;
}
