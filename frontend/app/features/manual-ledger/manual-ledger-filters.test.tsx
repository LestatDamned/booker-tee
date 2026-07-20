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
    expect(screen.getByLabelText("Описание")).toHaveValue("кофе");
    expect(screen.getByTestId("location-search")).toHaveTextContent("page=2");

    await user.clear(screen.getByLabelText("Описание"));
    await user.type(screen.getByLabelText("Описание"), "  аренда   июль  ");
    expect(screen.getByTestId("location-search")).toHaveTextContent(
      "search=кофе",
    );

    await user.click(screen.getByRole("button", { name: "Применить" }));
    expect(screen.getByTestId("location-search")).toHaveTextContent(
      "type=expense&search=%D0%B0%D1%80%D0%B5%D0%BD%D0%B4%D0%B0+%D0%B8%D1%8E%D0%BB%D1%8C&page=1&per_page=25",
    );
  });

  it("drops invalid URL values and uses normalized server pagination", () => {
    const draft = manualLedgerFilterDraft(
      "?type=wrong&account_id=wrong&date_from=wrong&per_page=999",
      filterOptions,
      200,
    );

    expect(draft.operationType).toBe("");
    expect(draft.accountId).toBe("");
    expect(draft.dateFrom).toBe("");
    expect(draft.perPage).toBe("200");
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
      <ManualLedgerFilters options={filterOptions} paginationPerPage={25} />
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
