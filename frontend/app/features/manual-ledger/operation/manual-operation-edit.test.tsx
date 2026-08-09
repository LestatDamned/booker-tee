import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ManualOperationEdit } from "./manual-operation-edit";

const operationId = "61f1e242-9b4a-43e8-b9f8-4fb0627f771a";
const accountId = "3d0ba2b5-a853-47b8-b76b-42ea6b30ce8f";
const destinationAccountId = "2b78e790-f82f-46e7-814a-d22f9d7455c2";

afterEach(() => vi.unstubAllGlobals());

describe("manual operation editing", () => {
  it("announces the local loading state while the edit snapshot is pending", async () => {
    let resolveRequest: ((response: Response) => void) | undefined;
    const pendingResponse = new Promise<Response>((resolve) => {
      resolveRequest = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => pendingResponse),
    );
    renderEdit({});

    const loading = screen.getByRole("status");
    expect(loading).toHaveAttribute("aria-busy", "true");
    expect(loading).toHaveTextContent("Загружаем актуальные данные…");

    resolveRequest?.(jsonResponse(editSnapshot(), 200));
    expect(await screen.findByLabelText("Описание")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("loads a fresh edit snapshot when the panel mounts", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(editSnapshot(), 200));
    vi.stubGlobal("fetch", fetchMock);
    renderEdit({});

    expect(await screen.findByLabelText("Описание")).toHaveValue(
      "Аренда за июль",
    );
    expect(screen.getByRole("button", { name: "Отмена" })).toHaveAttribute(
      "data-tone",
      "secondary",
    );
    expect(
      screen
        .getByRole("button", { name: "Сохранить изменения" })
        .querySelector("svg"),
    ).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("submits the loaded version and preserves a 422 draft", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(editSnapshot(), 200))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "validation_error",
              message: "Проверьте переданные данные.",
              fieldErrors: {
                "expense.amount": ["Сумма должна быть больше нуля."],
              },
            },
          },
          422,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderEdit({});

    const amount = await screen.findByLabelText(/^Сумма/);
    await user.clear(amount);
    await user.type(amount, "0");
    await user.click(
      screen.getByRole("button", { name: "Сохранить изменения" }),
    );

    expect(
      await screen.findAllByText("Сумма должна быть больше нуля."),
    ).toHaveLength(1);
    expect(amount).toHaveValue("0");
    expect(amount).toHaveFocus();
    expect(requestBody(fetchMock.mock.calls[1])).toEqual({
      amount: "0",
      operationDate: "2026-07-20",
      description: "Аренда за июль",
      version: 3,
      operationType: "expense",
      accountId,
      categoryId: null,
      propertyId: null,
    });
  });

  it("preserves an edit draft across a network failure and retry", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(editSnapshot(), 200))
      .mockRejectedValueOnce(new TypeError("Network unavailable"))
      .mockResolvedValueOnce(
        jsonResponse(
          editSnapshot({ description: "Retry", version: 4 }).operation,
          200,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderEdit({});

    const description = await screen.findByLabelText("Описание");
    await user.clear(description);
    await user.type(description, "Retry");
    await user.click(
      screen.getByRole("button", { name: "Сохранить изменения" }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Не удалось сохранить изменения");
    expect(alert).toHaveTextContent("Backend недоступен.");
    expect(description).toHaveValue("Retry");
    await user.click(
      within(alert).getByRole("button", { name: "Повторить сохранение" }),
    );
    expect(requestBody(fetchMock.mock.calls[2])).toEqual(
      expect.objectContaining({ description: "Retry", version: 3 }),
    );
  });

  it("keeps the stale draft on 409 until the user reloads the snapshot", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(editSnapshot(), 200))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "operation_version_conflict",
              message: "Операция уже изменилась в другом окне.",
            },
          },
          409,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          editSnapshot({ description: "Изменено во втором окне", version: 4 }),
          200,
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderEdit({});

    const description = await screen.findByLabelText("Описание");
    await user.clear(description);
    await user.type(description, "Мой конфликтующий draft");
    await user.click(
      screen.getByRole("button", { name: "Сохранить изменения" }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Операция уже была изменена");
    expect(alert).toHaveTextContent("Операция уже изменилась в другом окне.");
    expect(description).toHaveValue("Мой конфликтующий draft");
    await user.click(
      within(alert).getByRole("button", {
        name: "Загрузить актуальную версию",
      }),
    );

    expect(await screen.findByLabelText("Описание")).toHaveValue(
      "Изменено во втором окне",
    );
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("preserves list filters and targets the updated operation after success", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(editSnapshot(), 200))
      .mockResolvedValueOnce(
        jsonResponse(editSnapshot({ version: 4 }).operation, 200),
      )
      .mockResolvedValueOnce(
        jsonResponse(editSnapshot({ version: 5 }).operation, 200),
      );
    vi.stubGlobal("fetch", fetchMock);
    renderEdit({ withLocation: true });

    await screen.findByLabelText("Описание");
    await user.click(
      screen.getByRole("button", { name: "Сохранить изменения" }),
    );

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        `/ledger/manual?type=expense&page=2&operation_id=${operationId}#operation-${operationId}`,
      ),
    );
    const updateOptions = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(updateOptions.method).toBe("PUT");
    expect(updateOptions.headers).toEqual(
      expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
    );

    await user.click(
      screen.getByRole("button", { name: "Сохранить изменения" }),
    );
    expect(requestBody(fetchMock.mock.calls[2])).toEqual(
      expect.objectContaining({ version: 4 }),
    );
  });

  it("updates a transfer without income and expense references", async () => {
    const user = userEvent.setup();
    const snapshot = transferEditSnapshot();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(snapshot, 200))
      .mockResolvedValueOnce(jsonResponse(snapshot.operation, 200));
    vi.stubGlobal("fetch", fetchMock);
    renderEdit({});

    await screen.findByLabelText("Счёт списания *");
    expect(screen.queryByLabelText("Категория")).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Сохранить изменения" }),
    );

    expect(requestBody(fetchMock.mock.calls[1])).toEqual({
      amount: "5000.00",
      operationDate: "2026-07-20",
      description: "На накопительный",
      version: 5,
      operationType: "transfer",
      sourceAccountId: accountId,
      destinationAccountId,
    });
  });
});

function renderEdit({ withLocation = false }: { withLocation?: boolean }) {
  return render(editTree({ withLocation }));
}

function editTree({ withLocation = false }: { withLocation?: boolean }) {
  return (
    <MemoryRouter initialEntries={["/ledger/manual?type=expense&page=2"]}>
      <ManualOperationEdit
        csrfToken="csrf-token"
        onClose={vi.fn()}
        operationId={operationId}
      />
      {withLocation ? <LocationProbe /> : null}
    </MemoryRouter>
  );
}

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.pathname}
      {location.search}
      {location.hash}
    </output>
  );
}

function editSnapshot({
  description = "Аренда за июль",
  version = 3,
}: { description?: string; version?: number } = {}) {
  return {
    operation: {
      id: operationId,
      version,
      operationType: "expense",
      operationDate: "2026-07-20",
      description,
      status: "confirmed",
      money: {
        amount: "65000.00",
        currency: "RUB",
      },
      account: { id: accountId, name: "Основной счёт" },
      sourceAccount: null,
      destinationAccount: null,
      category: null,
      property: null,
      capabilities: {
        canEdit: true,
        canCancel: true,
        canRestore: false,
        canDelete: false,
        readonlyReason: null,
      },
    },
    filterOptions: {
      accounts: [accountOption(accountId, "Основной счёт")],
      categories: [],
      properties: [],
      perPage: [25, 50],
    },
  };
}

function transferEditSnapshot() {
  const snapshot = editSnapshot({
    description: "На накопительный",
    version: 5,
  });
  return {
    ...snapshot,
    operation: {
      ...snapshot.operation,
      operationType: "transfer",
      money: {
        amount: "5000.00",
        currency: "RUB",
      },
      account: null,
      sourceAccount: { id: accountId, name: "Основной счёт" },
      destinationAccount: {
        id: destinationAccountId,
        name: "Накопительный счёт",
      },
      category: null,
      property: null,
    },
    filterOptions: {
      ...snapshot.filterOptions,
      accounts: [
        accountOption(accountId, "Основной счёт"),
        accountOption(destinationAccountId, "Накопительный счёт"),
      ],
    },
  };
}

function accountOption(id: string, name: string) {
  return {
    id,
    name,
    currency: "RUB",
    canRecordIncome: true,
    canRecordExpense: true,
    canTransfer: true,
  };
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

function requestBody(call: unknown[] | undefined): unknown {
  if (!call) {
    throw new Error("Expected fetch call.");
  }
  return JSON.parse(String((call[1] as RequestInit).body));
}
