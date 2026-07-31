import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { SessionDto } from "../../api/session";
import type { ImportDocumentListDto } from "./api/import-documents-api";
import {
  formatStatementPeriod,
  ImportDocumentListPage,
} from "./import-document-list-page";

describe("ImportDocumentListPage", () => {
  it("renders an actionable, accessible document list", () => {
    renderPage(populatedDocuments);

    expect(
      screen.getByRole("heading", { name: "Импорты" }),
    ).toBeInTheDocument();
    const table = screen.getByRole("table");
    expect(within(table).getByText("Требует внимания")).toBeInTheDocument();
    expect(within(table).getByText("Основной")).toBeInTheDocument();
    expect(within(table).getByText("Альфа-Банк")).toBeInTheDocument();
    expect(within(table).getByText("Июль 2026")).toBeInTheDocument();
    expect(
      within(table).getByRole("link", { name: "Настроить" }),
    ).toHaveAttribute(
      "href",
      `/app/imports/documents/${mappingDocumentId}/mapping`,
    );
    expect(
      within(table).getByRole("link", { name: "Проверить" }),
    ).toHaveAttribute(
      "href",
      `/app/imports/documents/${reviewDocumentId}/review`,
    );
    expect(
      within(table).getByRole("link", { name: "Открыть" }),
    ).toHaveAttribute("href", `/app/imports/documents/${failedDocumentId}`);
  });

  it("renders an upload empty state for an import manager", () => {
    renderPage({
      ...populatedDocuments,
      items: [],
      pagination: { ...populatedDocuments.pagination, total: 0 },
      summary: { totalDocumentCount: 0, attentionDocumentCount: 0 },
    });

    expect(screen.getByText("Документов пока нет")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Загрузить выписку" }),
    ).toHaveAttribute("href", "/app/imports/upload");
    expect(
      screen.getByRole("link", { name: "Загрузить выписку" }),
    ).toHaveAttribute("data-tone", "primary");
  });

  it("keeps viewer data visible and hides upload mutations", () => {
    renderPage({
      ...populatedDocuments,
      capabilities: {
        canUpload: false,
        readonlyReasonCode: "import_management_forbidden",
      },
    });

    expect(screen.getByText("Режим только для чтения")).toBeInTheDocument();
    expect(screen.getAllByText("unknown.xlsx")).toHaveLength(2);
    expect(
      screen.queryByRole("link", { name: "Загрузить выписку" }),
    ).not.toBeInTheDocument();
  });

  it("distinguishes an empty filtered result from an empty workspace", () => {
    renderPage(
      {
        ...populatedDocuments,
        items: [],
        pagination: { ...populatedDocuments.pagination, total: 0 },
      },
      "/imports?state=completed",
    );

    expect(
      screen.getByText("По этим фильтрам документов нет"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Сбросить фильтры" }),
    ).toHaveAttribute("href", "/imports");
  });

  it("formats full and partial statement periods without timezone shifts", () => {
    expect(
      formatStatementPeriod({ start: "2026-07-01", end: "2026-07-31" }),
    ).toBe("Июль 2026");
    expect(
      formatStatementPeriod({ start: "2026-07-12", end: "2026-07-24" }),
    ).toBe("12–24 июля 2026");
    expect(formatStatementPeriod(null)).toBe("Не определён");
  });
});

function renderPage(
  documents: ImportDocumentListDto,
  initialEntry = "/imports",
) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <ImportDocumentListPage documents={documents} session={session} />
    </MemoryRouter>,
  );
}

const mappingDocumentId = "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8";
const reviewDocumentId = "cb1b2959-b134-4a57-b2f4-7a7dfe8e8a42";
const failedDocumentId = "74d26880-543e-459f-a2a2-9f1a497914fe";

const populatedDocuments: ImportDocumentListDto = {
  workspaceId: "c12c9ac8-6851-4467-b87a-da7fc70586c8",
  workspaceName: "Дом",
  items: [
    {
      id: mappingDocumentId,
      filename: "unknown.xlsx",
      status: "requires_review",
      createdAt: "2026-07-24T10:00:00Z",
      fileSizeBytes: 2048,
      detectedBankName: "Неизвестный банк",
      statementPeriod: null,
      account: null,
      totalRowCount: 0,
      reviewableRowCount: 0,
      capabilities: {
        canOpenDetail: true,
        canMap: true,
        canReview: false,
      },
      nextStepKind: "mapping",
    },
    {
      id: reviewDocumentId,
      filename: "known.pdf",
      status: "parsed",
      createdAt: "2026-07-23T10:00:00Z",
      fileSizeBytes: 4096,
      detectedBankName: "Альфа-Банк",
      statementPeriod: { start: "2026-07-01", end: "2026-07-31" },
      account: {
        id: "4958dd80-af47-4131-8f16-16c0ca04f63c",
        name: "Основной",
        currency: "RUB",
        bankName: "Альфа-Банк",
      },
      totalRowCount: 12,
      reviewableRowCount: 4,
      capabilities: {
        canOpenDetail: true,
        canMap: false,
        canReview: true,
      },
      nextStepKind: "review",
    },
    {
      id: failedDocumentId,
      filename: "failed.pdf",
      status: "failed_to_parse",
      createdAt: "2026-07-22T10:00:00Z",
      fileSizeBytes: null,
      detectedBankName: null,
      statementPeriod: null,
      account: null,
      totalRowCount: 0,
      reviewableRowCount: 0,
      capabilities: {
        canOpenDetail: true,
        canMap: false,
        canReview: false,
      },
      nextStepKind: "detail",
    },
  ],
  pagination: {
    page: 1,
    perPage: 25,
    total: 3,
    totalPages: 1,
    hasPrevious: false,
    hasNext: false,
  },
  filterOptions: {
    accounts: [
      {
        id: "4958dd80-af47-4131-8f16-16c0ca04f63c",
        name: "Основной",
        currency: "RUB",
        bankName: "Альфа-Банк",
      },
    ],
    perPage: [25, 50, 100],
  },
  summary: { totalDocumentCount: 3, attentionDocumentCount: 2 },
  capabilities: { canUpload: true, readonlyReasonCode: null },
};

const session: SessionDto = {
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
