import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ComponentType } from "react";

import type { AuthConfigResult } from "../features/users/api/auth-api";
import ForgotPasswordRoute from "./auth-forgot-password";
import ResetPasswordRoute from "./auth-reset-password";

const TestResetPasswordRoute = ResetPasswordRoute as ComponentType<{
  loaderData: AuthConfigResult;
}>;

const { requestResetMock, resetPasswordMock } = vi.hoisted(() => ({
  requestResetMock: vi.fn(),
  resetPasswordMock: vi.fn(),
}));

vi.mock("../features/users/api/auth-api", async (importOriginal) => ({
  ...(await importOriginal()),
  requestPasswordReset: requestResetMock,
  resetPassword: resetPasswordMock,
}));

describe("password recovery routes", () => {
  beforeEach(() => {
    requestResetMock.mockReset();
    resetPasswordMock.mockReset();
  });

  it("shows the generic accepted state after requesting recovery", async () => {
    requestResetMock.mockResolvedValue({
      status: "success",
      message: "Если аккаунт существует, письмо отправлено.",
      retryAfterSeconds: 60,
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <ForgotPasswordRoute />
      </MemoryRouter>,
    );

    await user.type(
      screen.getByRole("textbox", { name: /Email/ }),
      "max@example.test",
    );
    await user.click(screen.getByRole("button", { name: "Получить ссылку" }));

    expect(requestResetMock).toHaveBeenCalledWith({
      email: "max@example.test",
    });
    expect(screen.getByText("Проверьте почту")).toBeInTheDocument();
  });

  it("uses configured password minimum and validates confirmation", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter
        initialEntries={["/auth/reset-password?token=opaque-token"]}
      >
        <TestResetPasswordRoute
          loaderData={{
            status: "success",
            registrationMode: "open",
            passwordMinLength: 12,
          }}
        />
      </MemoryRouter>,
    );

    const password = screen.getByLabelText(/Новый пароль/);
    expect(password).toHaveAttribute("minlength", "12");
    await user.type(password, "long enough password");
    await user.type(
      screen.getByLabelText(/Повторите пароль/),
      "different password",
    );
    await user.click(screen.getByRole("button", { name: "Изменить пароль" }));

    expect(screen.getByText("Пароли не совпадают.")).toBeInTheDocument();
    expect(resetPasswordMock).not.toHaveBeenCalled();
  });
});
