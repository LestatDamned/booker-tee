import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { describe, expect, it } from "vitest";

import type { ManualLedgerDto } from "./manual-ledger-api";
import {
  ManualLedgerFilters,
  manualLedgerFilterDraft,
  manualLedgerFiltersAreActive,
} from "./manual-ledger-filters";

describe("ManualLedgerFilters", () => {
  it("keeps draft controls separate from the applied URL until Apply", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter
        initialEntries={[
          "/ledger/manual?type=expense&search=кофе&page=2&per_page=25",
        ]}
      >
        <FilterHarness />
      </MemoryRouter>,
    );

    expect(screen.getByLabelText("Тип")).toHaveValue("expense");
    expect(screen.getByTestId("location-search")).toHaveTextContent("page=2");

    await user.selectOptions(screen.getByLabelText("Статус"), "confirmed");
    expect(screen.getByTestId("location-search")).toHaveTextContent(
      "type=expense&search=кофе&page=2&per_page=25",
    );

    await user.click(screen.getByRole("button", { name: "Применить" }));
    expect(screen.getByTestId("location-search")).toHaveTextContent(
      "type=expense&status=confirmed&search=%D0%BA%D0%BE%D1%84%D0%B5&page=1&per_page=25",
    );
  });

  it("drops invalid URL values and uses normalized server pagination", () => {
    const draft = manualLedgerFilterDraft(
      "?type=wrong&account_id=wrong&date_from=wrong&per_page=999",
      filterOptions,
    );

    expect(draft.operationType).toBe("");
    expect(draft.accountId).toBe("");
    expect(draft.dateFrom).toBe("");
    expect(
      manualLedgerFiltersAreActive(
        "?type=wrong&date_from=wrong&account_id=wrong",
      ),
    ).toBe(false);
  });
});

function FilterHarness() {
  const location = useLocation();
  return (
    <>
      <ManualLedgerFilters
        onClose={() => undefined}
        options={filterOptions}
        perPage={25}
      />
      <output data-testid="location-search">{location.search}</output>
    </>
  );
}

const filterOptions: ManualLedgerDto["filterOptions"] = {
  accounts: [
    {
      id: "123e4567-e89b-12d3-a456-426614174000",
      name: "Основной счёт",
      currency: "RUB",
    },
  ],
  categories: [],
  properties: [],
  perPage: [25, 50, 100, 200],
};
