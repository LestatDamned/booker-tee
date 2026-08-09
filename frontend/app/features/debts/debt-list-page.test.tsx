import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createDebt } from "./api/debts-api";
import { DebtListPage } from "./debt-list-page";
import { account, detail, portfolio, session } from "./test-support";

vi.mock("./api/debts-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/debts-api")>();
  return { ...actual, createDebt: vi.fn() };
});

describe("DebtListPage", () => {
  beforeEach(() => vi.mocked(createDebt).mockReset());

  it("keeps currency totals separate and renders the active portfolio", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "Долги" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "RUB" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "USD" })).toBeVisible();
    expect(screen.getAllByText("Кредит на ремонт")).toHaveLength(2);
    expect(screen.getAllByLabelText(/75.*000,00 RUB/).length).toBeGreaterThan(
      0,
    );
    expect(
      screen.getByRole("button", { name: "Добавить долг" }),
    ).toHaveAttribute("data-tone", "primary");
  });

  it("validates and submits an existing debt", async () => {
    const user = userEvent.setup();
    vi.mocked(createDebt).mockResolvedValue({ status: "success", detail });
    renderPage();

    await user.click(screen.getByRole("button", { name: "Добавить долг" }));
    const dialog = screen.getByRole("dialog", { name: "Добавить долг" });
    await user.click(
      within(dialog).getByRole("button", { name: "Добавить долг" }),
    );
    expect(screen.getByText("Введите название долга.")).toBeVisible();
    expect(screen.getByLabelText(/Название/)).toHaveFocus();

    await user.type(screen.getByLabelText(/Название/), "Старый кредит");
    await user.type(screen.getByLabelText(/Текущий остаток/), "75000");
    await user.type(screen.getByLabelText(/Первоначальная сумма/), "100000");
    await user.click(
      within(dialog).getByRole("button", { name: "Добавить долг" }),
    );

    expect(createDebt).toHaveBeenCalledWith(
      expect.objectContaining({
        action: "add_existing",
        currency: "RUB",
        name: "Старый кредит",
        openingBalance: "75000",
        originalPrincipal: "100000",
      }),
      "csrf-token",
      expect.any(String),
    );
  });

  it("does not render write controls for a viewer", () => {
    renderPage({
      ...portfolio,
      capabilities: {
        canCreate: false,
        readonlyReasonCode: "financial_write_forbidden",
      },
    });

    expect(
      screen.getByText("Долги доступны только для просмотра"),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Добавить долг" }),
    ).not.toBeInTheDocument();
  });
});

function renderPage(value = portfolio) {
  return render(
    <MemoryRouter initialEntries={["/debts"]}>
      <DebtListPage accounts={[account]} portfolio={value} session={session} />
    </MemoryRouter>,
  );
}
