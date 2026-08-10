import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  importReviewPayload,
  reviewDocumentId,
} from "../features/import-review/test-support";
import { loadImportReviewRoute } from "./import-review-loader";
import { ImportReviewRouteView } from "./import-review";

describe("import review route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads session and document review in parallel", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/v1/session") {
        return Promise.resolve(jsonResponse(sessionPayload));
      }
      if (url === `/api/v1/import-review/${reviewDocumentId}`) {
        return Promise.resolve(jsonResponse(importReviewPayload()));
      }
      return Promise.resolve(new Response(null, { status: 404 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await loadImportReviewRoute(reviewDocumentId);

    expect(result.session.status).toBe("authenticated");
    expect(result.review.status).toBe("success");
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("renders not found without leaking workspace details", () => {
    render(
      <MemoryRouter>
        <ImportReviewRouteView
          loaderData={{
            session: { status: "authenticated", session: sessionPayload },
            review: { status: "not-found" },
          }}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "Документ не найден" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/другому workspace/)).toBeInTheDocument();
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
    type: "personal" as const,
    defaultCurrency: "RUB",
  },
  membership: { role: "owner" as const, status: "active" as const },
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
  csrfToken: "csrf-token",
};
