import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../api/session";
import type { ImportDocumentDetailDto } from "./api/import-document-detail-api";
import { ImportDocumentDetailPage } from "./import-document-detail-page";

vi.mock("./api/import-document-detail-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("./api/import-document-detail-api")>();
  return {
    ...actual,
    mutateImportDocument: vi.fn(),
  };
});

describe("ImportDocumentDetailPage", () => {
  it("leads with identity, next decision and validation evidence", () => {
    renderPage(documentFixture);

    expect(
      screen.getByRole("heading", { name: "Основной счёт" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        name: "Строки готовы к вашей проверке",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Перейти к проверке" }),
    ).toHaveAttribute(
      "href",
      `/app/imports/documents/${documentFixture.id}/review`,
    );
    expect(
      screen.getByRole("link", { name: "Перейти к проверке" }),
    ).toHaveAttribute("data-tone", "primary");
    expect(screen.getByText("Сверка сошлась")).toBeInTheDocument();
    expect(screen.getByText("1 200,00 ₽")).toBeInTheDocument();
    expect(screen.getByText("Покупка продуктов")).toBeInTheDocument();
    expect(screen.queryByText("private/storage.pdf")).not.toBeInTheDocument();
  });

  it("requires confirmation before deleting a document", async () => {
    const user = userEvent.setup();
    renderPage(documentFixture);

    await user.click(screen.getByRole("button", { name: "Удалить" }));

    const dialog = screen.getByRole("dialog", { name: "Удалить выписку?" });
    expect(
      within(dialog).getByRole("button", { name: "Удалить документ" }),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: "Отмена" }),
    ).toHaveFocus();
  });

  it("routes an unknown statement to column mapping", () => {
    renderPage({
      ...documentFixture,
      nextStep: "mapping",
      workflow: {
        upload: "done",
        extract: "done",
        mapping: "current",
        review: "pending",
        ledger: "pending",
      },
      validation: {
        ...documentFixture.validation!,
        status: "needs_mapping",
        reasonCode: "needs_mapping",
        needsMapping: true,
        tableCount: 2,
      },
      rawRows: { items: [], total: 0, limit: 10 },
    });

    expect(
      screen.getByRole("link", { name: "Настроить колонки" }),
    ).toHaveAttribute(
      "href",
      `/app/imports/documents/${documentFixture.id}/mapping`,
    );
    expect(
      screen.getByText(/таблицы с операциями найдены/),
    ).toBeInTheDocument();
  });

  it("opens failure evidence and offers a recoverable next step", () => {
    renderPage({
      ...documentFixture,
      status: "failed_to_parse",
      nextStep: "upload",
      workflow: {
        upload: "done",
        extract: "blocked",
        mapping: "pending",
        review: "pending",
        ledger: "pending",
      },
      validation: null,
      rawRows: { items: [], total: 0, limit: 10 },
      parseAttempts: {
        ...documentFixture.parseAttempts,
        items: [
          {
            ...documentFixture.parseAttempts.items[0]!,
            status: "failed",
            message: "Файл повреждён.",
          },
        ],
      },
    });

    expect(
      screen.getByRole("link", { name: "Загрузить другую" }),
    ).toHaveAttribute("href", "/app/imports/upload");
    expect(screen.getByText("Файл повреждён.")).toBeVisible();
    expect(
      screen.getByText("Из этой версии файла строки не извлечены."),
    ).toBeInTheDocument();
  });

  it("explains server-owned blocking reasons instead of only hiding actions", async () => {
    renderPage({
      ...documentFixture,
      capabilities: {
        ...documentFixture.capabilities,
        ignore: {
          allowed: false,
          blockingReasonCodes: ["linked_operations_exist"],
        },
        delete: {
          allowed: false,
          blockingReasonCodes: ["linked_operations_exist"],
        },
      },
    });

    expect(screen.getByText(/связан с операциями/)).toBeInTheDocument();
  });

  it("presents ignored rows as an explained difference, not an error", () => {
    renderPage({
      ...documentFixture,
      validation: {
        ...documentFixture.validation!,
        status: "mismatch",
        reasonCode: "ignored_rows_explain_mismatch",
        message: "Итоги по строкам не совпадают с итогами выписки.",
        ignoredRowCount: 1,
        ignoredTotalInflow: "250.00",
      },
    });

    expect(screen.getByText("Разница объяснена")).toBeInTheDocument();
    expect(screen.getByText(/Необъяснённой разницы нет/)).toBeInTheDocument();
    expect(
      screen.queryByText("Итоги по строкам не совпадают с итогами выписки."),
    ).not.toBeInTheDocument();
  });

  it("presents an imported document as completed instead of pending review", () => {
    renderPage({
      ...documentFixture,
      status: "imported",
      workflow: {
        upload: "done",
        extract: "done",
        mapping: "skipped",
        review: "done",
        ledger: "done",
      },
    });

    expect(
      screen.getByRole("heading", { name: "Импорт завершён" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Посмотреть результат" }),
    ).toHaveAttribute(
      "href",
      `/app/imports/documents/${documentFixture.id}/review`,
    );
    expect(
      screen.queryByText("Строки готовы к вашей проверке"),
    ).not.toBeInTheDocument();
  });

  it("keeps the full bank description visible in the readonly preview", () => {
    const description =
      "Списание средств по транзакции №177979632694 от 28/06/2026 в KRASNOE&BELOE по карте 220147XXXXXX5017";
    renderPage({
      ...documentFixture,
      rawRows: {
        ...documentFixture.rawRows,
        items: [{ ...documentFixture.rawRows.items[0]!, description }],
      },
    });

    expect(screen.getByText(description)).toBeVisible();
  });
});

function renderPage(document: ImportDocumentDetailDto) {
  return render(
    <MemoryRouter>
      <ImportDocumentDetailPage
        initialDocument={document}
        session={sessionFixture}
      />
    </MemoryRouter>,
  );
}

const documentFixture: ImportDocumentDetailDto = {
  id: "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8",
  filename: "statement-unknown-name.pdf",
  status: "requires_review",
  bankName: "Альфа-Банк",
  statementType: "account_statement",
  statementPeriodStart: "2026-07-01",
  statementPeriodEnd: "2026-07-31",
  fileSizeBytes: 2048,
  createdAt: "2026-07-24T10:00:00Z",
  updatedAt: "2026-07-24T10:01:00Z",
  account: {
    id: "4958dd80-af47-4131-8f16-16c0ca04f63c",
    name: "Основной счёт",
    currency: "RUB",
  },
  workflow: {
    upload: "done",
    extract: "done",
    mapping: "skipped",
    review: "current",
    ledger: "pending",
  },
  nextStep: "review",
  validation: {
    status: "valid",
    reasonCode: "totals_match",
    message: "Контрольные суммы совпали.",
    extractedCount: 1,
    calculatedTotalInflow: "1200.00",
    calculatedTotalOutflow: "0.00",
    ignoredRowCount: 0,
    ignoredTotalInflow: "0.00",
    ignoredTotalOutflow: "0.00",
    currency: "RUB",
    tableCount: null,
    needsMapping: false,
  },
  rawRows: {
    total: 1,
    limit: 10,
    items: [
      {
        rowIndex: 1,
        status: "normalized",
        displayDate: "2026-07-15",
        amount: "-450.00",
        amountRaw: "-450.00",
        currency: "RUB",
        description: "Покупка продуктов",
        normalizationError: "",
      },
    ],
  },
  parseAttempts: {
    total: 1,
    limit: 10,
    items: [
      {
        id: "b5fa14d0-3921-431d-83d8-714676f5c299",
        status: "success",
        parserName: "bank_statement",
        parserVersion: "1",
        startedAt: "2026-07-24T10:00:00Z",
        finishedAt: "2026-07-24T10:01:00Z",
        message: "",
      },
    ],
  },
  capabilities: {
    canManage: true,
    ignore: { allowed: true, blockingReasonCodes: [] },
    delete: { allowed: true, blockingReasonCodes: [] },
  },
};

const sessionFixture: SessionDto = {
  user: {
    id: "f4835818-f111-41d6-a59d-62f541ace357",
    email: "max@example.test",
    name: "Max",
  },
  workspace: {
    id: "c12c9ac8-6851-4467-b87a-da7fc70586c8",
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
