import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  operationsFixture,
  operationFixture,
} from "../features/operations/test-support";
import { session } from "../features/workspaces/test-support";
import tagStyles from "../ui/tag/tag.module.css";
import { OperationsRouteView } from "./operations";
import { loadOperationsRoute } from "./operations-loader";

describe("operations route", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("passes URL state to the unified API", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session")
        return Promise.resolve(jsonResponse(session));
      if (
        url ===
        "/api/v1/operations?source=bank_pdf&page=2&operation_id=3d0ba2b5-a853-47b8-b76b-42ea6b30ce8f"
      ) {
        return Promise.resolve(jsonResponse(operationsFixture()));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadOperationsRoute(
      new Request(
        "http://localhost/app/operations?source=bank_pdf&page=2&operation_id=3d0ba2b5-a853-47b8-b76b-42ea6b30ce8f",
      ),
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.operations.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("renders all sources and exposes only source-aware edit actions", () => {
    const operations = operationsFixture();
    renderRoute(operations);

    expect(screen.getByRole("heading", { name: "Операции" })).toBeVisible();
    const expectedSources = ["Вручную", "Импорт", "Долг", "Система"];
    operations.items.forEach((operation, index) => {
      expect(
        document.getElementById(`operation-${operation.id}`),
      ).toHaveTextContent(expectedSources[index]!);
    });
    expect(screen.getAllByRole("button", { name: "Исправить" })).toHaveLength(
      2,
    );
    expect(screen.getAllByRole("link", { name: "Операции" })).toHaveLength(2);
  });

  it("focuses a deep-linked row and exposes its source in actions", async () => {
    const user = userEvent.setup();
    const operations = operationsFixture();
    const imported = operations.items[1]!;
    operations.targetOperationId = imported.id;
    operations.targetOperation = imported;

    renderRoute(
      operations,
      false,
      `/app/operations?operation_id=${imported.id}`,
    );

    const row = document.getElementById(`operation-${imported.id}`)!;
    expect(row).toHaveFocus();
    expect(row).toHaveTextContent(`${imported.account?.name} · Импорт`);
    expect(
      screen.queryByRole("region", { name: "Детали операции" }),
    ).not.toBeInTheDocument();
    await user.click(within(row).getByRole("button", { name: "Ещё действия" }));
    expect(
      screen.getByRole("link", { name: "Открыть импорт" }),
    ).toHaveAttribute(
      "href",
      `/imports/documents/${imported.provenance?.kind === "import" ? imported.provenance.uploadedDocumentId : ""}/review#raw-${imported.provenance?.kind === "import" ? imported.provenance.rawTransactionId : ""}`,
    );
  });

  it("routes imported correction through the imported operation endpoint", async () => {
    const user = userEvent.setup();
    const operations = operationsFixture();
    const imported = operations.items[1]!;
    const fetchMock = vi.fn<typeof fetch>(() =>
      Promise.resolve(new Response(null, { status: 500 })),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderRoute(operations);

    const importedRow = document.getElementById(`operation-${imported.id}`)!;
    await user.click(
      within(importedRow).getByRole("button", { name: "Исправить" }),
    );
    await user.type(
      within(importedRow).getByLabelText("Описание"),
      " уточнено",
    );
    await user.click(
      within(importedRow).getByRole("button", {
        name: "Сохранить исправления",
      }),
    );

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `/api/v1/accounts/${imported.account?.id}/operations/${imported.id}/review-fields`,
    );
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({ method: "PUT" });
  });

  it("keeps debt and system operations read-only with a recovery path", () => {
    const operations = operationsFixture();
    const debt = operations.items[2]!;
    const system = operations.items[3]!;
    operations.targetOperationId = debt.id;
    operations.targetOperation = debt;
    renderRoute(operations, false, `/app/operations?operation_id=${debt.id}`);

    const debtRow = document.getElementById(`operation-${debt.id}`)!;
    expect(within(debtRow).getByText("Долг")).toHaveClass(
      tagStyles.tag!,
      tagStyles.soft!,
    );
    expect(
      within(debtRow).getByText("Долг").querySelector("svg"),
    ).not.toBeNull();
    expect(debtRow).not.toHaveTextContent(`${debt.account?.name} · Долг`);
    expect(
      within(debtRow).getByRole("link", { name: "Открыть долг" }),
    ).toHaveAttribute(
      "href",
      `/debts/${debt.provenance?.kind === "debt" ? debt.provenance.debtAccountId : ""}`,
    );
    expect(
      within(document.getElementById(`operation-${system.id}`)!).queryByRole(
        "button",
        { name: "Исправить" },
      ),
    ).not.toBeInTheDocument();
    expect(debtRow).toHaveTextContent(
      "Изменения выполняются в исходном разделе",
    );
  });

  it("renders a targeted operation outside the current page", () => {
    const operations = operationsFixture();
    const target = operationFixture("debt", "Старый платёж по долгу");
    operations.items = operations.items.slice(0, 1);
    operations.targetOperationId = target.id;
    operations.targetOperation = target;

    renderRoute(operations);

    expect(screen.getByText("Старый платёж по долгу")).toBeVisible();
    expect(
      document.getElementById(`operation-${target.id}`),
    ).toBeInTheDocument();
  });

  it("writes the source filter into URL state", async () => {
    const user = userEvent.setup();
    renderRoute(operationsFixture(), true);

    await user.click(screen.getByRole("button", { name: "Показать фильтры" }));
    await user.click(screen.getByText("Ещё фильтры"));
    await user.selectOptions(screen.getByLabelText("Источник"), "bank_pdf");
    await user.click(screen.getByRole("button", { name: "Применить" }));

    expect(screen.getByTestId("location-search")).toHaveTextContent(
      "source=bank_pdf&page=1&per_page=50",
    );
  });

  it("uses operation type as the primary URL-backed classification", async () => {
    const user = userEvent.setup();
    renderRoute(operationsFixture(), true);

    await user.click(screen.getByRole("link", { name: "Расходы" }));

    expect(screen.getByTestId("location-search")).toHaveTextContent(
      "type=expense&page=1",
    );
  });

  it("renders a recoverable route error", () => {
    render(
      <MemoryRouter>
        <OperationsRouteView
          loaderData={{
            session: { status: "authenticated", session },
            operations: { status: "error", message: "Backend недоступен." },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Backend недоступен.");
    expect(screen.getByRole("link", { name: "Повторить" })).toBeVisible();
  });
});

function renderRoute(
  operations: ReturnType<typeof operationsFixture>,
  showLocation = false,
  initialEntry = "/app/operations",
) {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <OperationsRouteView
        loaderData={{
          session: { status: "authenticated", session },
          operations: { status: "success", operations },
        }}
      />
      {showLocation ? <LocationProbe /> : null}
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location-search">{location.search}</output>;
}

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}
