import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { AccountPage } from "./profile-account";

describe("account lifecycle page", () => {
  it("reads an email-change token from the URL fragment", () => {
    render(
      <MemoryRouter
        initialEntries={["/profile/account#token=marker-email-change-token"]}
      >
        <AccountPage
          csrfToken="csrf-token"
          currentEmail="max@example.test"
          impact={{
            canDeactivate: true,
            blockers: [],
            autoDeactivatedWorkspaceCount: 1,
          }}
        />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("button", { name: "Подтвердить изменение" }),
    ).toBeInTheDocument();
  });

  it("blocks deactivation and links shared ownership to workspace settings", () => {
    render(
      <MemoryRouter initialEntries={["/profile/account"]}>
        <AccountPage
          csrfToken="csrf-token"
          currentEmail="max@example.test"
          impact={{
            canDeactivate: false,
            blockers: [
              {
                workspaceId: "7d71f4c7-ea92-45d4-817a-a1d85d509d4c",
                workspaceName: "Семья",
                activeOtherMemberCount: 2,
              },
            ],
            autoDeactivatedWorkspaceCount: 1,
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Семья")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Управлять владельцем и состоянием" }),
    ).toHaveAttribute(
      "href",
      "/workspaces/7d71f4c7-ea92-45d4-817a-a1d85d509d4c/settings",
    );
    expect(
      screen.getByRole("button", { name: "Деактивировать аккаунт" }),
    ).toBeDisabled();
    expect(
      screen.getByText(/Финансовые записи сохранятся/),
    ).toBeInTheDocument();
  });
});
