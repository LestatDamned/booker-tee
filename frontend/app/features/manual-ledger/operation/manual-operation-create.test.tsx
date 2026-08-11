import { useRef, useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ManualOperationCreate } from "./manual-operation-create";

const accountId = "3d0ba2b5-a853-47b8-b76b-42ea6b30ce8f";
const destinationAccountId = "2b78e790-f82f-46e7-814a-d22f9d7455c2";
const creditCardId = "40dfb587-8080-44d8-ac21-89cc74fbbb21";
const categoryId = "9e74db13-c89a-4e00-9d23-8a61e0e61cc0";
const propertyId = "de28f72f-aad9-4a54-abf9-b3c8972d950c";
const operationId = "61f1e242-9b4a-43e8-b9f8-4fb0627f771a";

afterEach(() => vi.unstubAllGlobals());

describe("manual operation creation", () => {
  it("requires an explicit financial operation type", async () => {
    const user = userEvent.setup();
    renderCreate();

    await user.click(screen.getByRole("button", { name: "Добавить операцию" }));

    expect(screen.getByRole("radio", { name: "Доход" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Расход" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Перевод" })).not.toBeChecked();
    expect(
      screen.getByRole("button", { name: "Создать операцию" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Отмена" })).toHaveAttribute(
      "data-tone",
      "secondary",
    );

    await user.click(screen.getByRole("radio", { name: "Расход" }));
    expect(
      screen.getByRole("button", { name: "Создать расход" }),
    ).toBeEnabled();
  });

  it("offers a credit card only for an expense", async () => {
    const user = userEvent.setup();
    renderCreate();

    await user.click(screen.getByRole("button", { name: "Добавить операцию" }));
    await user.click(screen.getByRole("radio", { name: "Расход" }));
    await user.selectOptions(screen.getByLabelText("Счёт *"), creditCardId);
    expect(screen.getByLabelText("Счёт *")).toHaveValue(creditCardId);

    await user.click(screen.getByRole("radio", { name: "Перевод" }));
    expect(screen.getByLabelText("Счёт списания *")).toHaveValue("");
    expect(
      screen.queryByRole("option", { name: "Кредитная карта" }),
    ).not.toBeInTheDocument();
  });

  it("sends decimal-string JSON with CSRF and navigates to the server result", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(createdIncome(), 201));
    vi.stubGlobal("fetch", fetchMock);
    renderCreate();

    await user.click(screen.getByRole("button", { name: "Добавить операцию" }));
    await user.click(screen.getByRole("radio", { name: "Доход" }));
    await user.selectOptions(screen.getByLabelText("Счёт *"), accountId);
    await user.type(screen.getByLabelText(/^Сумма/), "1250,50");
    fireEvent.change(screen.getByLabelText("Дата *"), {
      target: { value: "2026-07-20" },
    });
    await user.click(screen.getByRole("combobox", { name: "Категория" }));
    await user.type(
      screen.getByRole("combobox", { name: "Категория" }),
      "проц",
    );
    await user.click(screen.getByRole("option", { name: "Проценты" }));
    await user.selectOptions(screen.getByLabelText("Объект"), propertyId);
    await user.type(screen.getByLabelText("Описание"), "Проценты по вкладу");
    await user.click(screen.getByRole("button", { name: "Создать доход" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/manual-ledger",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Idempotency-Key": expect.any(String),
          "X-CSRF-Token": "csrf-token",
        }),
      }),
    );
    expect(requestBody(fetchMock.mock.calls[0])).toEqual({
      operationType: "income",
      accountId,
      amount: "1250,50",
      operationDate: "2026-07-20",
      description: "Проценты по вкладу",
      categoryId,
      propertyId,
    });
    expect(await screen.findByTestId("location")).toHaveTextContent(
      `/operations?operation_id=${operationId}#operation-${operationId}`,
    );
    expect(
      screen.queryByRole("button", { name: "Создать доход" }),
    ).not.toBeInTheDocument();
  });

  it("preserves the draft and associates a 422 error with its field", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "validation_error",
              message: "Проверьте переданные данные.",
              fieldErrors: {
                "income.amount": ["Сумма должна быть больше нуля."],
              },
            },
          },
          422,
        ),
      ),
    );
    renderCreate();

    await user.click(screen.getByRole("button", { name: "Добавить операцию" }));
    await user.click(screen.getByRole("radio", { name: "Доход" }));
    await user.selectOptions(screen.getByLabelText("Счёт *"), accountId);
    await user.type(screen.getByLabelText(/^Сумма/), "0");
    await user.type(screen.getByLabelText("Описание"), "Несохранённый доход");
    await user.click(screen.getByRole("button", { name: "Создать доход" }));

    expect(
      await screen.findByText("Сумма должна быть больше нуля."),
    ).toBeVisible();
    expect(screen.getByLabelText(/^Сумма/)).toHaveValue("0");
    expect(screen.getByLabelText("Описание")).toHaveValue(
      "Несохранённый доход",
    );
    expect(screen.getByLabelText(/^Сумма/)).toHaveAttribute(
      "aria-describedby",
      "manual-operation-amount-error",
    );
    expect(screen.getByLabelText(/^Сумма/)).toHaveFocus();
  });

  it("keeps one pending request and restores the disclosure focus on cancel", async () => {
    const user = userEvent.setup();
    let resolveRequest: ((response: Response) => void) | undefined;
    const pendingResponse = new Promise<Response>((resolve) => {
      resolveRequest = resolve;
    });
    const fetchMock = vi.fn().mockReturnValue(pendingResponse);
    vi.stubGlobal("fetch", fetchMock);
    renderCreate();

    const disclosure = screen.getByRole("button", {
      name: "Добавить операцию",
    });
    await user.click(disclosure);
    await user.click(screen.getByRole("radio", { name: "Доход" }));
    await user.selectOptions(screen.getByLabelText("Счёт *"), accountId);
    await user.type(screen.getByLabelText(/^Сумма/), "10");
    const form = document.getElementById("manual-operation-create-panel");
    if (!(form instanceof HTMLFormElement)) {
      throw new Error("Create form was not rendered.");
    }
    fireEvent.submit(form);
    fireEvent.submit(form);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(
      screen.getByRole("button", { name: "Создать доход" }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Отмена" })).toBeDisabled();
    resolveRequest?.(jsonResponse(createdIncome(), 201));
    await waitFor(() =>
      expect(screen.queryByLabelText(/^Сумма/)).not.toBeInTheDocument(),
    );

    await user.click(disclosure);
    await user.click(screen.getByRole("button", { name: "Отмена" }));
    await waitFor(() => expect(disclosure).toHaveFocus());
  });

  it("preserves the draft and idempotency key across a network retry", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Network unavailable"))
      .mockResolvedValueOnce(jsonResponse(createdIncome(), 201));
    vi.stubGlobal("fetch", fetchMock);
    renderCreate();

    await user.click(screen.getByRole("button", { name: "Добавить операцию" }));
    await user.click(screen.getByRole("radio", { name: "Доход" }));
    await user.selectOptions(screen.getByLabelText("Счёт *"), accountId);
    await user.type(screen.getByLabelText(/^Сумма/), "10");
    await user.type(screen.getByLabelText("Описание"), "Сетевой retry");
    await user.click(screen.getByRole("button", { name: "Создать доход" }));

    expect(await screen.findByText("Backend недоступен.")).toBeVisible();
    expect(screen.getByLabelText("Описание")).toHaveValue("Сетевой retry");
    await user.click(screen.getByRole("button", { name: "Создать доход" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(requestHeaders(fetchMock.mock.calls[0])["Idempotency-Key"]).toBe(
      requestHeaders(fetchMock.mock.calls[1])["Idempotency-Key"],
    );
  });

  it("uses the same controlled draft to create an expense", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(createdOperation("expense"), 201));
    vi.stubGlobal("fetch", fetchMock);
    renderCreate();

    await user.click(screen.getByRole("button", { name: "Добавить операцию" }));
    await user.click(screen.getByRole("radio", { name: "Расход" }));
    await user.selectOptions(screen.getByLabelText("Счёт *"), accountId);
    await user.type(screen.getByLabelText(/^Сумма/), "881.12");
    fireEvent.change(screen.getByLabelText("Дата *"), {
      target: { value: "2026-07-21" },
    });
    await user.type(screen.getByLabelText("Описание"), "Коммунальные услуги");
    await user.click(screen.getByRole("button", { name: "Создать расход" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(requestBody(fetchMock.mock.calls[0])).toEqual({
      operationType: "expense",
      accountId,
      amount: "881.12",
      operationDate: "2026-07-21",
      description: "Коммунальные услуги",
      categoryId: null,
      propertyId: null,
    });
  });

  it("creates a transfer with distinct account fields and reuses the retry key", async () => {
    const user = userEvent.setup();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: "transfer_currency_mismatch",
              message: "Для перевода выберите счета в одной валюте.",
              fieldErrors: {
                destinationAccountId: [
                  "Для перевода выберите счета в одной валюте.",
                ],
              },
            },
          },
          422,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(createdOperation("transfer"), 201));
    vi.stubGlobal("fetch", fetchMock);
    renderCreate();

    await user.click(screen.getByRole("button", { name: "Добавить операцию" }));
    await user.click(screen.getByRole("radio", { name: "Перевод" }));
    expect(screen.queryByLabelText("Категория")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Объект")).not.toBeInTheDocument();
    await user.selectOptions(
      screen.getByLabelText("Счёт списания *"),
      accountId,
    );
    await user.selectOptions(
      screen.getByLabelText("Счёт зачисления *"),
      destinationAccountId,
    );
    await user.type(screen.getByLabelText(/^Сумма/), "5000");
    await user.type(screen.getByLabelText("Описание"), "На накопительный");
    await user.click(screen.getByRole("button", { name: "Создать перевод" }));

    expect(
      await screen.findAllByText("Для перевода выберите счета в одной валюте."),
    ).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Создать перевод" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const firstHeaders = requestHeaders(fetchMock.mock.calls[0]);
    const secondHeaders = requestHeaders(fetchMock.mock.calls[1]);
    expect(firstHeaders["Idempotency-Key"]).toBe(
      secondHeaders["Idempotency-Key"],
    );
    const secondRequest = fetchMock.mock.calls[1]?.[1] as RequestInit;
    expect(JSON.parse(String(secondRequest.body))).toEqual({
      operationType: "transfer",
      sourceAccountId: accountId,
      destinationAccountId,
      amount: "5000",
      operationDate: expect.any(String),
      description: "На накопительный",
    });
  });

  it("does not expose a mutation control to a readonly member", () => {
    renderCreate({ canCreate: false });

    expect(
      screen.queryByRole("button", { name: "Добавить операцию" }),
    ).not.toBeInTheDocument();
  });
});

function renderCreate({ canCreate = true }: { canCreate?: boolean } = {}) {
  return render(
    <MemoryRouter initialEntries={["/operations"]}>
      <CreateHarness
        canCreate={canCreate}
        csrfToken="csrf-token"
        options={{
          accounts: [
            {
              id: accountId,
              name: "Основной счёт",
              currency: "RUB",
              canRecordIncome: true,
              canRecordExpense: true,
              canTransfer: true,
            },
            {
              id: destinationAccountId,
              name: "Накопительный счёт",
              currency: "RUB",
              canRecordIncome: true,
              canRecordExpense: true,
              canTransfer: true,
            },
            {
              id: creditCardId,
              name: "Кредитная карта",
              currency: "RUB",
              canRecordIncome: false,
              canRecordExpense: true,
              canTransfer: false,
            },
          ],
          categories: [{ id: categoryId, name: "Проценты" }],
          properties: [{ id: propertyId, name: "Квартира" }],
          perPage: [25, 50, 100, 200],
        }}
      />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function CreateHarness(
  props: Omit<React.ComponentProps<typeof ManualOperationCreate>, "onClose"> & {
    canCreate: boolean;
  },
) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const { canCreate, ...createProps } = props;
  function close() {
    setIsOpen(false);
    queueMicrotask(() => triggerRef.current?.focus());
  }
  return (
    <>
      {canCreate ? (
        <button onClick={() => setIsOpen(true)} ref={triggerRef}>
          Добавить операцию
        </button>
      ) : null}
      {isOpen ? (
        <ManualOperationCreate {...createProps} onClose={close} />
      ) : null}
    </>
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

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

function createdIncome() {
  return createdOperation("income");
}

function createdOperation(operationType: "income" | "expense" | "transfer") {
  return {
    id: operationId,
    version: 1,
    operationType,
    operationDate: "2026-07-20",
    description: "Проценты по вкладу",
    status: "confirmed",
    money: {
      amount: "1250.50",
      currency: "RUB",
    },
    account:
      operationType === "transfer"
        ? null
        : { id: accountId, name: "Основной счёт" },
    sourceAccount:
      operationType === "transfer"
        ? { id: accountId, name: "Основной счёт" }
        : null,
    destinationAccount:
      operationType === "transfer"
        ? { id: destinationAccountId, name: "Накопительный счёт" }
        : null,
    category:
      operationType === "transfer"
        ? null
        : { id: categoryId, name: "Проценты" },
    property:
      operationType === "transfer"
        ? null
        : { id: propertyId, name: "Квартира" },
    capabilities: {
      canEdit: true,
      canCancel: true,
      canRestore: false,
      canDelete: false,
      readonlyReason: null,
    },
  };
}

function requestHeaders(call: unknown[] | undefined): Record<string, string> {
  const request = requestOptions(call);
  return request.headers as Record<string, string>;
}

function requestBody(call: unknown[] | undefined): unknown {
  const request = requestOptions(call);
  return JSON.parse(String(request.body));
}

function requestOptions(call: unknown[] | undefined): RequestInit {
  if (!call) {
    throw new Error("Expected fetch call.");
  }
  return call[1] as RequestInit;
}
