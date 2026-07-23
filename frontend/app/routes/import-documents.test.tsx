import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ImportDocumentsRouteView } from "./import-documents";
import { loadImportDocumentsRoute } from "./import-documents-loader";

describe("import documents route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads session and documents in parallel", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse(sessionPayload));
      }
      if (
        url ===
        "/api/v1/imports/documents?state=attention&account_id=4958dd80-af47-4131-8f16-16c0ca04f63c&page=2"
      ) {
        return Promise.resolve(jsonResponse(documentsPayload));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadImportDocumentsRoute(
      new Request(
        "http://localhost/app/imports?state=attention&account_id=4958dd80-af47-4131-8f16-16c0ca04f63c&page=2&ignored=value",
      ),
    );

    expect(result.session.status).toBe("authenticated");
    expect(result.documents.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("renders login when either request is unauthenticated", () => {
    render(
      <MemoryRouter>
        <ImportDocumentsRouteView
          loaderData={{
            session: { status: "unauthenticated" },
            documents: { status: "unauthenticated" },
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/login?next=/app/imports",
    );
  });
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  });
}

const sessionPayload = {
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

const documentsPayload = {
  workspaceId: "c12c9ac8-6851-4467-b87a-da7fc70586c8",
  workspaceName: "Дом",
  items: [],
  pagination: {
    page: 1,
    perPage: 25,
    total: 0,
    totalPages: 1,
    hasPrevious: false,
    hasNext: false,
  },
  filterOptions: { accounts: [], perPage: [25, 50, 100] },
  summary: { totalDocumentCount: 0, attentionDocumentCount: 0 },
  capabilities: { canUpload: true, readonlyReasonCode: null },
};
