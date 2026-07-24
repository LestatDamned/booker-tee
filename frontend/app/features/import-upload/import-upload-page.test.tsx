import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SessionDto } from "../../api/session";
import type { ImportUploadReferenceDto } from "./api/import-upload-api";
import { uploadImportDocument } from "./api/import-upload-api";
import { ImportUploadPage } from "./import-upload-page";

const navigate = vi.fn();

vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return { ...actual, useNavigate: () => navigate };
});

vi.mock("./api/import-upload-api", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("./api/import-upload-api")>();
  return { ...actual, uploadImportDocument: vi.fn() };
});

describe("ImportUploadPage", () => {
  beforeEach(() => {
    navigate.mockReset();
    vi.mocked(uploadImportDocument).mockReset();
  });

  it("requires an explicit account and statement file", async () => {
    const user = userEvent.setup();
    renderPage(reference);

    await user.click(screen.getByRole("button", { name: "Загрузить выписку" }));

    expect(screen.getByText("Выберите счёт выписки.")).toBeInTheDocument();
    expect(screen.getByText("Выберите файл выписки.")).toBeInTheDocument();
    expect(uploadImportDocument).not.toHaveBeenCalled();
  });

  it("keeps the draft and navigates to the committed document", async () => {
    const user = userEvent.setup();
    vi.mocked(uploadImportDocument).mockResolvedValue({
      status: "success",
      document: {
        id: "3a2616cb-9f56-4b6e-8ae8-b5b16bd16f73",
        status: "requires_review",
        replayed: false,
        navigationTarget: "document_detail",
        nextStep: "review",
      },
    });
    renderPage(reference);

    await user.selectOptions(
      screen.getByRole("combobox", { name: /Счёт выписки/ }),
      reference.accounts[0]!.id,
    );
    await user.upload(
      screen.getByLabelText(/Файл выписки/),
      new File(["statement"], "statement.pdf", { type: "application/pdf" }),
    );
    await user.click(screen.getByRole("button", { name: "Загрузить выписку" }));

    await waitFor(() =>
      expect(navigate).toHaveBeenCalledWith(
        "/imports/documents/3a2616cb-9f56-4b6e-8ae8-b5b16bd16f73",
      ),
    );
    expect(uploadImportDocument).toHaveBeenCalledWith(
      expect.objectContaining({
        accountId: reference.accounts[0]!.id,
        csrfToken: "csrf-token",
      }),
    );
  });

  it("explains the no-account and readonly states", () => {
    const { rerender } = renderPage({ ...reference, accounts: [] });
    expect(
      screen.getByRole("heading", { name: "Сначала создайте счёт" }),
    ).toBeInTheDocument();

    rerender(
      <MemoryRouter>
        <ImportUploadPage
          reference={{ ...reference, canUpload: false }}
          session={session}
        />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("heading", { name: "Загрузка недоступна" }),
    ).toBeInTheDocument();
  });

  it("rejects an unsupported file before the request", async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderPage(reference);
    await user.selectOptions(
      screen.getByRole("combobox", { name: /Счёт выписки/ }),
      reference.accounts[0]!.id,
    );
    await user.upload(
      screen.getByLabelText(/Файл выписки/),
      new File(["text"], "statement.txt", { type: "text/plain" }),
    );
    await user.click(screen.getByRole("button", { name: "Загрузить выписку" }));

    expect(screen.getAllByText(/Поддерживаются только/)).toHaveLength(2);
    expect(uploadImportDocument).not.toHaveBeenCalled();
  });
});

function renderPage(currentReference: ImportUploadReferenceDto) {
  return render(
    <MemoryRouter>
      <ImportUploadPage reference={currentReference} session={session} />
    </MemoryRouter>,
  );
}

const reference: ImportUploadReferenceDto = {
  accounts: [
    {
      id: "a4c41cef-1b88-49cb-85eb-402f09b5c836",
      name: "Основной",
      currency: "RUB",
      bankName: "Экспобанк",
    },
  ],
  acceptedExtensions: [".pdf", ".xlsx"],
  acceptedContentTypes: [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ],
  maxFileSizeBytes: 20 * 1024 * 1024,
  canUpload: true,
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
  membership: {
    role: "owner",
    status: "active",
  },
  capabilities: {
    canReadWorkspace: true,
    canWriteFinancialData: true,
    canManageImports: true,
    canManageMembers: true,
    canManageWorkspace: true,
  },
  csrfToken: "csrf-token",
};
