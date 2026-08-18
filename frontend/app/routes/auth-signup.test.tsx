import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ComponentType } from "react";

import SignupRoute from "./auth-signup";
import type { AuthConfigResult } from "../features/users/api/auth-api";

const TestSignupRoute = SignupRoute as ComponentType<{
  loaderData: AuthConfigResult;
}>;

const { resendMock, signupMock } = vi.hoisted(() => ({
  resendMock: vi.fn(),
  signupMock: vi.fn(),
}));

vi.mock("../features/users/api/auth-api", async (importOriginal) => ({
  ...(await importOriginal()),
  resendEmailVerification: resendMock,
  signup: signupMock,
}));

describe("SignupRoute", () => {
  beforeEach(() => {
    signupMock.mockReset();
    resendMock.mockReset();
  });

  it("keeps native form semantics and shows the generic accepted state", async () => {
    signupMock.mockResolvedValue({
      status: "success",
      message: "Если адрес подходит, письмо отправлено.",
      retryAfterSeconds: 60,
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter
        initialEntries={[
          "/auth/signup#invitation=private-token&next=%2Fapp%2Fprofile",
        ]}
      >
        <TestSignupRoute
          loaderData={{
            status: "success",
            registrationMode: "invite_only",
            passwordMinLength: 12,
          }}
        />
      </MemoryRouter>,
    );

    const email = screen.getByRole("textbox", { name: /Email/ });
    const password = screen.getByLabelText(/Пароль/);
    expect(email).toHaveAttribute("autocomplete", "email");
    expect(password).toHaveAttribute("autocomplete", "new-password");
    expect(password).toHaveAttribute("minlength", "12");

    await user.type(email, "max@example.test");
    await user.type(password, "correct horse battery staple");
    await user.click(screen.getByRole("button", { name: "Создать аккаунт" }));

    expect(signupMock).toHaveBeenCalledWith({
      email: "max@example.test",
      name: null,
      password: "correct horse battery staple",
      nextPath: "/app/profile",
      invitationToken: "private-token",
    });
    expect(screen.getByText("Проверьте почту")).toBeInTheDocument();
    expect(screen.getByText("max@example.test")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Отправить повторно через 60/ }),
    ).toBeDisabled();
  });

  it("blocks invite-only registration without an invitation", () => {
    render(
      <MemoryRouter initialEntries={["/auth/signup"]}>
        <TestSignupRoute
          loaderData={{
            status: "success",
            registrationMode: "invite_only",
            passwordMinLength: 8,
          }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Регистрация по приглашению")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Создать аккаунт" }),
    ).not.toBeInTheDocument();
  });
});
