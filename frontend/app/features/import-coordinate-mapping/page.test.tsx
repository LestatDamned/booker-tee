import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../api/session";
import { redirectIfUnauthenticated } from "../../session/unauthenticated";
import {
  importCoordinates,
  loadCoordinatePageImage,
  previewCoordinates,
} from "./api";
import { VisualCoordinateMappingPage } from "./page";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  loadCoordinatePageImage: vi.fn(),
  previewCoordinates: vi.fn(),
  importCoordinates: vi.fn(),
}));
vi.mock("../../session/unauthenticated", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../session/unauthenticated")>()),
  redirectIfUnauthenticated: vi.fn(),
}));

describe("VisualCoordinateMappingPage capability", () => {
  beforeEach(() => {
    vi.mocked(loadCoordinatePageImage).mockReset();
    vi.mocked(loadCoordinatePageImage).mockReturnValue(
      new Promise<never>(() => {}),
    );
    vi.mocked(redirectIfUnauthenticated).mockReset();
    vi.mocked(previewCoordinates).mockReset();
    vi.mocked(importCoordinates).mockReset();
  });

  it("renders column mapping as a secondary page action", () => {
    renderAllowedPage();

    const link = screen.getByRole("link", { name: "Настройка колонок" });
    expect(link).toHaveAttribute(
      "href",
      "/imports/documents/document-id/mapping",
    );
    expect(link).toHaveAttribute("data-tone", "secondary");
    expect(link.closest("nav")).toHaveAccessibleName("Режим настройки импорта");
  });

  it("groups extraction settings and explains the example row", () => {
    renderAllowedPage();

    expect(
      screen.getByRole("heading", { name: "Настройки распознавания" }),
    ).toBeVisible();
    expect(
      screen.getByRole("group", { name: "Дополнительные поля" }),
    ).toBeVisible();
    expect(screen.getByLabelText("Формат суммы")).toBeVisible();
    expect(screen.getByLabelText("Готовый шаблон")).toBeVisible();
    expect(
      screen.getByText(/по этому примеру система распознает остальные строки/i),
    ).toBeVisible();
  });

  it.each(["source_missing", "pdf_required", "account_required"])(
    "renders %s without initializing a layout or requesting an image",
    (reason) => {
      render(
        <MemoryRouter>
          <VisualCoordinateMappingPage
            overview={{
              documentId: "document-id",
              filename: "statement.pdf",
              pageCount: 0,
              pages: [],
              defaultCurrency: "RUB",
              capability: { allowed: false, blockingReasonCodes: [reason] },
              templates: [],
            }}
            session={session}
          />
        </MemoryRouter>,
      );

      expect(
        screen.getByRole("heading", {
          name: "Визуальная настройка недоступна",
        }),
      ).toBeVisible();
      expect(screen.getByText(reason)).toBeVisible();
      expect(loadCoordinatePageImage).not.toHaveBeenCalled();
    },
  );

  it("redirects when preview observes an expired session", async () => {
    vi.mocked(previewCoordinates).mockResolvedValue({
      status: "unauthenticated",
    });
    vi.mocked(redirectIfUnauthenticated).mockReturnValue(true);
    renderAllowedPage();

    await userEvent.click(
      screen.getByRole("button", { name: "Обновить предпросмотр" }),
    );

    expect(redirectIfUnauthenticated).toHaveBeenCalledWith({
      status: "unauthenticated",
    });
  });

  it("marks preview stale after role changes and reuses the import key on retry", async () => {
    vi.mocked(previewCoordinates).mockResolvedValue({
      status: "success",
      value: {
        rows: [],
        totalRowCount: 1,
        validRowCount: 1,
        invalidRowCount: 0,
        rowLimit: 20,
        rowsTruncated: false,
        warnings: [],
        canImport: true,
      },
    });
    vi.mocked(importCoordinates).mockResolvedValue({
      status: "error",
      message: "retry",
    });
    renderAllowedPage();
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: "Обновить предпросмотр" }),
    );
    const importButton = screen.getByRole("button", {
      name: "Импортировать в проверку",
    });
    await user.click(importButton);
    await user.click(importButton);
    expect(vi.mocked(importCoordinates).mock.calls[0]?.[4]).toBe(
      vi.mocked(importCoordinates).mock.calls[1]?.[4],
    );

    await user.click(screen.getByRole("checkbox", { name: "Валюта" }));
    expect(
      screen.getByRole("heading", { name: "Предпросмотр устарел" }),
    ).toBeVisible();
    expect(importButton).toBeDisabled();
  });

  it("shows every warning while preserving server import availability", async () => {
    vi.mocked(previewCoordinates).mockResolvedValue({
      status: "success",
      value: {
        rows: [
          {
            pageNumber: 1,
            sourceRowNumber: 1,
            layout: "first",
            operationDateRaw: "01.08.2026",
            operationDate: "2026-08-01",
            postingDateRaw: "",
            postingDate: null,
            descriptionRaw: "Первая страница",
            description: "Первая страница",
            amountRaw: "-100",
            amount: "-100",
            currencyRaw: "",
            currency: "RUB",
            balanceAfterRaw: "",
            balanceAfter: null,
            status: "valid",
            errors: [],
          },
        ],
        totalRowCount: 1,
        validRowCount: 1,
        invalidRowCount: 0,
        rowLimit: 20,
        rowsTruncated: false,
        warnings: [
          {
            code: "coordinate_date_anchors_missing",
            severity: "warning",
            fields: [],
            affectedRowCount: 1,
          },
          {
            code: "high_error_rate",
            severity: "warning",
            fields: [],
            affectedRowCount: null,
          },
        ],
        canImport: true,
      },
    });
    renderAllowedPage(2);

    await userEvent.click(
      screen.getByRole("button", { name: "Обновить предпросмотр" }),
    );

    const warnings = screen.getByRole("list", {
      name: "Предупреждения предпросмотра",
    });
    expect(warnings).toHaveTextContent(
      "На странице не найдены строки с датами",
    );
    expect(warnings).toHaveTextContent("затронуто: 1");
    expect(warnings).toHaveTextContent("Много строк требуют проверки");
    expect(screen.getByText(/Первая страница/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Импортировать в проверку" }),
    ).toBeEnabled();
  });

  it("allows a viewer to preview but never enables coordinate import", async () => {
    vi.mocked(previewCoordinates).mockResolvedValue({
      status: "success",
      value: {
        rows: [],
        totalRowCount: 1,
        validRowCount: 1,
        invalidRowCount: 0,
        rowLimit: 20,
        rowsTruncated: false,
        warnings: [],
        canImport: true,
      },
    });
    renderAllowedPage(1, [], {
      ...session,
      membership: { role: "viewer", status: "active" },
      capabilities: { ...session.capabilities, canManageImports: false },
    });
    const user = userEvent.setup();

    await user.click(
      screen.getByRole("button", { name: "Обновить предпросмотр" }),
    );

    expect(previewCoordinates).toHaveBeenCalledOnce();
    const importButton = screen.getByRole("button", {
      name: "Импортировать в проверку",
    });
    expect(importButton).toBeDisabled();
    await user.click(importButton);
    expect(importCoordinates).not.toHaveBeenCalled();
  });

  it("shows an image error and retry opens the editor", async () => {
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:page"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    vi.mocked(loadCoordinatePageImage)
      .mockResolvedValueOnce({ status: "error", message: "PDF недоступен" })
      .mockResolvedValueOnce({ status: "success", value: new Blob(["png"]) });
    renderAllowedPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "PDF недоступен",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Повторить загрузку страницы" }),
    );

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Переместить область Дата" }),
      ).toBeVisible(),
    );
  });

  it("redirects an unauthorized image request through the session contract", async () => {
    vi.mocked(loadCoordinatePageImage).mockResolvedValue({
      status: "unauthenticated",
    });
    vi.mocked(redirectIfUnauthenticated).mockReturnValue(true);
    renderAllowedPage();

    await waitFor(() =>
      expect(redirectIfUnauthenticated).toHaveBeenCalledWith({
        status: "unauthenticated",
      }),
    );
  });

  it("keeps the loaded editor when active layout or same-page template is selected", async () => {
    Object.defineProperty(URL, "createObjectURL", {
      configurable: true,
      value: vi.fn(() => "blob:page"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      configurable: true,
      value: vi.fn(),
    });
    vi.mocked(loadCoordinatePageImage).mockResolvedValue({
      status: "success",
      value: new Blob(["png"]),
    });
    renderAllowedPage(1, [singlePageTemplate]);
    const user = userEvent.setup();
    expect(
      await screen.findByRole("button", { name: "Переместить область Дата" }),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Первая" }));
    const templateSelect = screen.getByLabelText("Готовый шаблон");
    await user.selectOptions(templateSelect, "same-page-template");
    await user.selectOptions(templateSelect, "");

    expect(
      screen.getByRole("button", { name: "Переместить область Дата" }),
    ).toBeVisible();
    expect(templateSelect).toHaveValue("");
    expect(loadCoordinatePageImage).toHaveBeenCalledTimes(1);
  });

  it("resets an incompatible template to the current PDF draft", async () => {
    vi.mocked(previewCoordinates)
      .mockResolvedValueOnce({
        status: "error",
        message: "Page aspect ratio does not match the saved layout.",
      })
      .mockResolvedValueOnce({
        status: "success",
        value: {
          rows: [],
          totalRowCount: 1,
          validRowCount: 1,
          invalidRowCount: 0,
          rowLimit: 20,
          rowsTruncated: false,
          warnings: [],
          canImport: true,
        },
      });
    renderAllowedPage(1, [
      {
        id: "incompatible-template",
        name: "Incompatible template",
        spec: {
          version: 1,
          defaultCurrency: "RUB",
          unsignedAmountDirection: "require_sign",
          layouts: {
            first: {
              pageAspectRatio: 0.5,
              transactionTop: 0.1,
              transactionBottom: 0.9,
              sampleRow: { x0: 0.05, y0: 0.2, x1: 0.95, y1: 0.3 },
              fields: {
                operation_date: { x0: 0.05, y0: 0.2, x1: 0.2, y1: 0.3 },
                description: { x0: 0.25, y0: 0.2, x1: 0.65, y1: 0.3 },
                amount: { x0: 0.75, y0: 0.2, x1: 0.95, y1: 0.3 },
              },
            },
          },
        },
      },
    ]);
    const user = userEvent.setup();

    await user.selectOptions(
      screen.getByLabelText("Готовый шаблон"),
      "incompatible-template",
    );
    await user.click(
      screen.getByRole("button", { name: "Обновить предпросмотр" }),
    );

    expect(vi.mocked(previewCoordinates).mock.lastCall?.[1]).toMatchObject({
      layouts: { first: { pageAspectRatio: 0.5 } },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Page aspect ratio does not match the saved layout.",
    );
    expect(
      screen.getByRole("button", { name: "Импортировать в проверку" }),
    ).toBeDisabled();
    expect(importCoordinates).not.toHaveBeenCalled();

    await user.selectOptions(screen.getByLabelText("Готовый шаблон"), "");
    expect(screen.getByLabelText("Готовый шаблон")).toHaveValue("");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Обновить предпросмотр" }),
    );

    expect(vi.mocked(previewCoordinates).mock.lastCall?.[1]).toMatchObject({
      layouts: { first: { pageAspectRatio: 0.75 } },
    });
    expect(
      screen.getByRole("button", { name: "Импортировать в проверку" }),
    ).toBeEnabled();
  });

  it("applies a saved template and redirects after successful import", async () => {
    vi.mocked(previewCoordinates).mockResolvedValue({
      status: "success",
      value: {
        rows: [],
        totalRowCount: 1,
        validRowCount: 1,
        invalidRowCount: 0,
        rowLimit: 20,
        rowsTruncated: false,
        warnings: [],
        canImport: true,
      },
    });
    vi.mocked(importCoordinates).mockResolvedValue({
      status: "success",
      value: {
        documentId: "document-id",
        status: "requires_review",
        importedRowCount: 1,
        templateId: null,
        replayed: false,
        reviewTarget: { kind: "import_review", documentId: "document-id" },
      },
    });
    renderAllowedPage(3, [
      {
        id: "template-id",
        name: "Split template",
        spec: {
          version: 1,
          defaultCurrency: "RUB",
          unsignedAmountDirection: "require_sign",
          layouts: {
            first: {
              pageAspectRatio: 0.75,
              transactionTop: 0.1,
              transactionBottom: 0.9,
              sampleRow: { x0: 0.05, y0: 0.2, x1: 0.95, y1: 0.3 },
              fields: {
                operation_date: { x0: 0.05, y0: 0.2, x1: 0.2, y1: 0.3 },
                description: { x0: 0.25, y0: 0.2, x1: 0.55, y1: 0.3 },
                debit: { x0: 0.6, y0: 0.2, x1: 0.75, y1: 0.3 },
                credit: { x0: 0.8, y0: 0.2, x1: 0.95, y1: 0.3 },
              },
            },
          },
        },
      },
    ]);
    const user = userEvent.setup();
    await user.selectOptions(
      screen.getByLabelText("Готовый шаблон"),
      "template-id",
    );
    expect(screen.getByLabelText("Формат суммы")).toHaveValue("split");
    await user.click(
      screen.getByRole("button", { name: "Обновить предпросмотр" }),
    );
    await user.click(
      screen.getByRole("button", { name: "Импортировать в проверку" }),
    );

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/imports/documents/document-id/review",
      ),
    );
  });
});

function renderAllowedPage(
  pageCount = 1,
  templates: Parameters<
    typeof VisualCoordinateMappingPage
  >[0]["overview"]["templates"] = [],
  activeSession: SessionDto = session,
) {
  const pages = Array.from({ length: pageCount }, (_, index) => ({
    pageNumber: index + 1,
    width: 600,
    height: 800,
    aspectRatio: 0.75,
    hasTextLayer: true,
  }));
  render(
    <MemoryRouter>
      <VisualCoordinateMappingPage
        overview={{
          documentId: "document-id",
          filename: "statement.pdf",
          pageCount,
          pages,
          defaultCurrency: "RUB",
          capability: { allowed: true, blockingReasonCodes: [] },
          templates,
        }}
        session={activeSession}
      />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

const session = {
  user: { id: "user", email: "user@example.test", name: "User" },
  workspace: {
    id: "workspace",
    name: "Home",
    type: "personal",
    defaultCurrency: "RUB",
  },
  membership: { role: "owner", status: "active" },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: true,
    canManageImports: true,
    canViewRawImportData: true,
    canViewMemberDirectory: true,
    canManageMembers: true,
    canViewWorkspaceActivity: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf",
} satisfies SessionDto;

const singlePageTemplate = {
  id: "same-page-template",
  name: "Same page",
  spec: {
    version: 1 as const,
    defaultCurrency: "RUB",
    unsignedAmountDirection: "require_sign" as const,
    layouts: {
      first: {
        pageAspectRatio: 0.75,
        transactionTop: 0.1,
        transactionBottom: 0.9,
        sampleRow: { x0: 0.05, y0: 0.2, x1: 0.95, y1: 0.3 },
        fields: {
          operation_date: { x0: 0.05, y0: 0.2, x1: 0.2, y1: 0.3 },
          description: { x0: 0.25, y0: 0.2, x1: 0.65, y1: 0.3 },
          amount: { x0: 0.75, y0: 0.2, x1: 0.95, y1: 0.3 },
        },
      },
    },
  },
};
