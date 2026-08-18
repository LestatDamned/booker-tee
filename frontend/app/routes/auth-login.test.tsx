import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import LoginRoute from "./auth-login";

describe("LoginRoute", () => {
  it("uses native auth semantics and focuses the first invalid field", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/auth/login?next=/app/profile"]}>
        <LoginRoute />
      </MemoryRouter>,
    );

    const email = screen.getByRole("textbox", { name: /Email/ });
    const password = screen.getByLabelText(/Пароль/);
    expect(email).toHaveAttribute("type", "email");
    expect(email).toHaveAttribute("autocomplete", "email");
    expect(password).toHaveAttribute("autocomplete", "current-password");
    expect(password).toHaveAttribute("type", "password");

    await user.click(screen.getByRole("button", { name: "Показать" }));
    expect(password).toHaveAttribute("type", "text");

    await user.click(screen.getByRole("button", { name: "Войти" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Введите email");
    expect(email).toHaveFocus();
  });

  it("keeps invitation credentials in fragments between auth pages", () => {
    render(
      <MemoryRouter
        initialEntries={[
          "/auth/login#invitation=marker-token&next=%2Fapp%2Fworkspaces%2Finvitation%23token%3Dmarker-token",
        ]}
      >
        <LoginRoute />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: "Создать" })).toHaveAttribute(
      "href",
      "/auth/signup#invitation=marker-token&next=%2Fapp%2Fworkspaces%2Finvitation%23token%3Dmarker-token",
    );
  });
});
