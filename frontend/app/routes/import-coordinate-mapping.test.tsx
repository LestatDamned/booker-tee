import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import ImportCoordinateMappingRoute from "./import-coordinate-mapping";

describe("import coordinate mapping route", () => {
  it("links an expired session to the app login with the complete return path", () => {
    render(
      <MemoryRouter
        initialEntries={[
          "/app/imports/documents/document-id/coordinate-mapping?from=detail",
        ]}
      >
        <ImportCoordinateMappingRoute
          loaderData={{
            session: { status: "unauthenticated" },
            overview: { status: "unauthenticated" },
          }}
          params={{ documentId: "document-id" }}
          matches={[] as never}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Войти" })).toHaveAttribute(
      "href",
      "/app/auth/login?next=%2Fapp%2Fimports%2Fdocuments%2Fdocument-id%2Fcoordinate-mapping%3Ffrom%3Ddetail",
    );
  });
});
