import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ManualOperationDelete } from "./manual-operation-delete";

const operationId = "61f1e242-9b4a-43e8-b9f8-4fb0627f771a";

afterEach(() => vi.unstubAllGlobals());

describe("ManualOperationDelete", () => {
  it("requires explicit confirmation before the versioned DELETE", async () => {
    const user = userEvent.setup();
    const onDeleted = vi.fn();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ManualOperationDelete
        csrfToken="csrf-token"
        onDeleted={onDeleted}
        operationId={operationId}
        version={4}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "Удалить окончательно" }),
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByText(/без возможности восстановления/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Не удалять" }));
    expect(fetchMock).not.toHaveBeenCalled();

    await user.click(
      screen.getByRole("button", { name: "Удалить окончательно" }),
    );
    await user.click(screen.getByRole("button", { name: "Да, удалить" }));

    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith(operationId));
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/v1/manual-ledger/${operationId}`,
      expect.objectContaining({
        method: "DELETE",
        headers: expect.objectContaining({ "X-CSRF-Token": "csrf-token" }),
        body: JSON.stringify({ version: 4 }),
      }),
    );
  });

  it("keeps a delete conflict in the row until explicit refresh", async () => {
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "operation_version_conflict",
              message: "Операция уже изменилась в другом окне.",
            },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    render(
      <ManualOperationDelete
        csrfToken="csrf-token"
        onRefresh={onRefresh}
        operationId={operationId}
        version={4}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "Удалить окончательно" }),
    );
    await user.click(screen.getByRole("button", { name: "Да, удалить" }));
    expect(
      await screen.findByText("Операция уже изменилась в другом окне."),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Обновить строку" }));

    expect(onRefresh).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("button", { name: "Удалить окончательно" }),
    ).toBeVisible();
  });
});
