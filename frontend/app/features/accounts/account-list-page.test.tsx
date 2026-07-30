import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../api/session";
import {
  changeAccountLifecycle,
  createAccount,
  type AccountDirectoryDto,
} from "./api/accounts-api";
import { AccountListPage } from "./account-list-page";

vi.mock("./api/accounts-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api/accounts-api")>();
  return {
    ...actual,
    changeAccountLifecycle: vi.fn(),
    createAccount: vi.fn(),
  };
});

describe("AccountListPage", () => {
  beforeEach(() => {
    vi.mocked(createAccount).mockReset();
    vi.mocked(changeAccountLifecycle).mockReset();
  });

  it("renders authoritative balances without presenting them as income", () => {
    renderPage(directory);

    expect(screen.getAllByText("Основной")).toHaveLength(2);
    expect(screen.getAllByLabelText(/9.118,88 RUB/)).toHaveLength(2);
    expect(screen.queryByText("Активен")).not.toBeInTheDocument();
    expect(screen.getAllByText("4 проводки")).toHaveLength(2);
    expect(screen.getAllByRole("link", { name: "Открыть" })[0]).toHaveAttribute(
      "data-tone",
      "secondary",
    );
    expect(screen.getByRole("button", { name: "Новый счёт" })).toHaveAttribute(
      "data-tone",
      "primary",
    );
    expect(screen.getByText("1 счёт")).toBeInTheDocument();
  });

  it("keeps viewer in a readable state without create controls", () => {
    renderPage({
      ...directory,
      capabilities: {
        canCreate: false,
        readonlyReasonCode: "financial_write_forbidden",
      },
    });

    expect(
      screen.getByText("Счета доступны только для просмотра"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Создать счёт" }),
    ).not.toBeInTheDocument();
  });

  it("focuses and explains invalid create fields", async () => {
    const user = userEvent.setup();
    renderPage(directory);

    await user.click(screen.getByRole("button", { name: "Новый счёт" }));
    await user.clear(screen.getByLabelText(/Валюта/));
    await user.clear(screen.getByLabelText(/Начальный баланс/));
    await user.click(screen.getByRole("button", { name: "Создать счёт" }));

    expect(screen.getByText("Введите название счёта.")).toBeInTheDocument();
    expect(
      screen.getByText("Введите трёхбуквенный код валюты."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Введите сумму с точностью до двух знаков."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Название/)).toHaveFocus();
    expect(createAccount).not.toHaveBeenCalled();
  });

  it("adds only the committed account and resets the draft", async () => {
    const user = userEvent.setup();
    vi.mocked(createAccount).mockResolvedValue({
      status: "success",
      account: {
        id: "a8f6cdad-2b31-47f1-83f9-9494347cbdd7",
        name: "Резерв",
        accountType: "deposit",
        currency: "RUB",
        initialBalance: "1500.00",
        balance: "1500.00",
        balanceDirection: "positive",
        movementCount: 0,
        isActive: true,
        updatedAt: "2026-07-30T12:30:00Z",
        capabilities: { canArchive: true, canRestore: false },
      },
    });
    renderPage(directory);

    await user.click(screen.getByRole("button", { name: "Новый счёт" }));
    await user.type(screen.getByLabelText(/Название/), "Резерв");
    await user.selectOptions(screen.getByLabelText(/Тип/), "deposit");
    await user.clear(screen.getByLabelText(/Начальный баланс/));
    await user.type(screen.getByLabelText(/Начальный баланс/), "1500,00");
    await user.click(screen.getByRole("button", { name: "Создать счёт" }));

    await waitFor(() =>
      expect(screen.getByText("Счёт «Резерв» создан.")).toBeInTheDocument(),
    );
    expect(screen.getAllByText("Резерв")).toHaveLength(2);
    expect(createAccount).toHaveBeenCalledWith({
      csrfToken: "csrf-token",
      draft: {
        name: "Резерв",
        accountType: "deposit",
        currency: "RUB",
        initialBalance: "1500,00",
      },
    });
    expect(
      screen.queryByRole("dialog", { name: "Новый счёт" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Новый счёт" }));
    expect(screen.getByLabelText(/Название/)).toHaveValue("");
  });

  it("archives only after confirmation and reconciles the committed row", async () => {
    const user = userEvent.setup();
    const account = directory.items[0]!;
    vi.mocked(changeAccountLifecycle).mockResolvedValue({
      status: "success",
      account: {
        ...account,
        isActive: false,
        updatedAt: "2026-07-30T12:10:00Z",
        capabilities: { canArchive: false, canRestore: true },
      },
    });
    renderPage(directory);

    await user.click(screen.getAllByRole("button", { name: "В архив" })[0]!);

    expect(
      screen.getByRole("dialog", { name: "Перенести счёт в архив?" }),
    ).toBeInTheDocument();
    const archiveButtons = screen.getAllByRole("button", {
      name: "Перенести в архив",
    });
    await user.click(archiveButtons[archiveButtons.length - 1]!);

    await waitFor(() =>
      expect(changeAccountLifecycle).toHaveBeenCalledWith({
        account,
        action: "archive",
        csrfToken: "csrf-token",
      }),
    );
    expect(screen.getByRole("link", { name: "Архив 1" })).toBeInTheDocument();
    expect(screen.getByText("Активных счетов нет")).toBeInTheDocument();
  });
});

function renderPage(currentDirectory: AccountDirectoryDto) {
  return render(
    <MemoryRouter>
      <AccountListPage directory={currentDirectory} session={session} />
    </MemoryRouter>,
  );
}

const directory: AccountDirectoryDto = {
  items: [
    {
      id: "285c18d8-78bb-46d7-b6cd-d6fc897ab8a2",
      name: "Основной",
      accountType: "card",
      currency: "RUB",
      initialBalance: "10000.00",
      balance: "9118.88",
      balanceDirection: "positive",
      movementCount: 4,
      isActive: true,
      updatedAt: "2026-07-30T12:00:00Z",
      capabilities: { canArchive: true, canRestore: false },
    },
  ],
  accountTypes: ["cash", "card", "deposit", "checking", "other"],
  capabilities: { canCreate: true, readonlyReasonCode: null },
};

const session: SessionDto = {
  user: {
    id: "2290fe02-81cb-477e-a0e1-589783f8b316",
    email: "max@example.test",
    name: "Max",
  },
  workspace: {
    id: "53a112fc-8907-4692-8bf6-35128684b535",
    name: "Дом",
    type: "personal",
    defaultCurrency: "RUB",
  },
  membership: { role: "owner", status: "active" },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: true,
    canManageImports: true,
    canManageMembers: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};
