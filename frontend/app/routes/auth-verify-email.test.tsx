import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import VerifyEmailRoute from "./auth-verify-email";

const { resendMock, verifyMock } = vi.hoisted(() => ({
  resendMock: vi.fn(),
  verifyMock: vi.fn(),
}));

vi.mock("../features/users/api/auth-api", async (importOriginal) => ({
  ...(await importOriginal()),
  resendEmailVerification: resendMock,
  verifyEmail: verifyMock,
}));

describe("VerifyEmailRoute", () => {
  beforeEach(() => {
    resendMock.mockReset();
    verifyMock.mockReset();
  });

  it("removes the token from the URL before explicit confirmation", async () => {
    verifyMock.mockResolvedValue({
      status: "error",
      fieldErrors: {},
      message: "Ссылка недействительна или срок её действия истёк.",
    });
    const user = userEvent.setup();

    render(
      <MemoryRouter
        initialEntries={[
          "/auth/verify-email?token=secret-token&next=/app/profile",
        ]}
      >
        <VerifyEmailRoute />
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("location-search")).toHaveTextContent(
        "?next=%2Fapp%2Fprofile",
      ),
    );
    expect(verifyMock).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Подтвердить email" }));

    expect(verifyMock).toHaveBeenCalledWith({
      token: "secret-token",
      nextPath: "/app/profile",
    });
    expect(screen.getByRole("textbox", { name: /Email/ })).toHaveFocus();
    expect(screen.getByText("Нужна новая ссылка")).toBeInTheDocument();
  });
});

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location-search">{location.search}</output>;
}
