import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ManualOperationDelete } from "./manual-operation-delete";

const operationId = "61f1e242-9b4a-43e8-b9f8-4fb0627f771a";

afterEach(() => vi.unstubAllGlobals());

describe("manual operation deletion", () => {
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
    const dialog = screen.getByRole("dialog", { name: "Удалить операцию?" });
    expect(dialog).toHaveTextContent("без возможности восстановления");
    const cancel = within(dialog).getByRole("button", { name: "Не удалять" });
    const confirm = within(dialog).getByRole("button", {
      name: "Удалить навсегда",
    });
    expect(cancel).toHaveAttribute("data-tone", "secondary");
    expect(cancel).toHaveFocus();
    expect(cancel.compareDocumentPosition(confirm)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    );
    await user.click(cancel);
    expect(fetchMock).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Удалить окончательно" }),
      ).toHaveFocus(),
    );

    await user.click(
      screen.getByRole("button", { name: "Удалить окончательно" }),
    );
    await user.click(screen.getByRole("button", { name: "Удалить навсегда" }));

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
    await user.click(screen.getByRole("button", { name: "Удалить навсегда" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Операция уже была изменена");
    const refresh = within(alert).getByRole("button", {
      name: "Обновить строку",
    });
    expect(refresh).toHaveAttribute("data-tone", "secondary");
    await user.click(refresh);

    expect(onRefresh).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("button", { name: "Удалить окончательно" }),
    ).toBeVisible();
  });
});
