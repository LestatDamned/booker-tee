import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ManualOperationDto } from "../api/manual-ledger-api";
import { ManualOperationLifecycle } from "./manual-operation-lifecycle";

const operationId = "61f1e242-9b4a-43e8-b9f8-4fb0627f771a";

afterEach(() => vi.unstubAllGlobals());

describe("manual operation lifecycle", () => {
  it("sends the current version and reconciles from the server response", async () => {
    const user = userEvent.setup();
    const onUpdated = vi.fn();
    const updatedOperation = operation("ignored", 4);
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(updatedOperation, 200));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ManualOperationLifecycle
        action="cancel"
        csrfToken="csrf-token"
        onUpdated={onUpdated}
        operationId={operationId}
        version={3}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Отменить операцию" }));

    await waitFor(() =>
      expect(onUpdated).toHaveBeenCalledWith(updatedOperation),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/manual-ledger/${operationId}/cancel`,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
        body: JSON.stringify({ version: 3 }),
      }),
    );
  });

  it("keeps a lifecycle conflict local and offers an explicit refresh", async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "operation_version_conflict",
              message: "Операция уже изменилась в другом окне.",
            },
          },
          409,
        ),
      ),
    );
    render(
      <ManualOperationLifecycle
        action="restore"
        csrfToken="csrf-token"
        onRefresh={onRefresh}
        operationId={operationId}
        version={4}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "Восстановить операцию" }),
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Операция уже была изменена");
    const refresh = within(alert).getByRole("button", {
      name: "Обновить строку",
    });
    expect(refresh).toHaveAttribute("data-tone", "secondary");
    await user.click(refresh);

    expect(onRefresh).toHaveBeenCalledOnce();
    expect(
      screen.queryByText("Операция уже изменилась в другом окне."),
    ).not.toBeInTheDocument();
  });

  it("keeps the action available after a network failure and retries", async () => {
    const user = userEvent.setup();
    const onUpdated = vi.fn();
    const updatedOperation = operation("ignored", 4);
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Network unavailable"))
      .mockResolvedValueOnce(jsonResponse(updatedOperation, 200));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ManualOperationLifecycle
        action="cancel"
        csrfToken="csrf-token"
        onUpdated={onUpdated}
        operationId={operationId}
        version={3}
      />,
    );

    const action = screen.getByRole("button", { name: "Отменить операцию" });
    await user.click(action);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Не удалось выполнить действие");
    expect(alert).toHaveTextContent("Backend недоступен.");

    await user.click(within(alert).getByRole("button", { name: "Повторить" }));
    await waitFor(() =>
      expect(onUpdated).toHaveBeenCalledWith(updatedOperation),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

function operation(
  status: ManualOperationDto["status"],
  version: number,
): ManualOperationDto {
  const ignored = status === "ignored";
  return {
    id: operationId,
    version,
    operationType: "expense",
    operationDate: "2026-07-20",
    description: "Аренда за июль",
    status,
    money: {
      amount: "65000.00",
      currency: "RUB",
    },
    account: { id: crypto.randomUUID(), name: "Основной счёт" },
    sourceAccount: null,
    destinationAccount: null,
    category: null,
    property: null,
    capabilities: {
      canEdit: !ignored,
      canCancel: !ignored,
      canRestore: ignored,
      canDelete: ignored,
      readonlyReason: null,
    },
  };
}

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}
