import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { UserSessionDto } from "../features/users/api/account-api";
import { SessionsPage } from "./profile-sessions";

const { loadMock, revokeMock, revokeOthersMock } = vi.hoisted(() => ({
  loadMock: vi.fn(),
  revokeMock: vi.fn(),
  revokeOthersMock: vi.fn(),
}));

vi.mock("../features/users/api/account-api", async (importOriginal) => ({
  ...(await importOriginal()),
  loadUserSessions: loadMock,
  revokeOtherUserSessions: revokeOthersMock,
  revokeUserSession: revokeMock,
}));

const current: UserSessionDto = {
  id: "11111111-1111-4111-8111-111111111111",
  isCurrent: true,
  deviceSummary: "Chrome · Linux",
  createdAt: "2026-08-04T10:00:00Z",
  lastSeenAt: "2026-08-04T12:00:00Z",
  expiresAt: "2026-08-18T10:00:00Z",
};

const other: UserSessionDto = {
  ...current,
  id: "22222222-2222-4222-8222-222222222222",
  isCurrent: false,
  deviceSummary: "Safari · iPhone",
};

describe("profile sessions", () => {
  beforeEach(() => {
    loadMock.mockReset();
    revokeMock.mockReset();
    revokeOthersMock.mockReset();
  });

  it("marks current session and confirms revoking another session", async () => {
    revokeMock.mockResolvedValue({ status: "success" });
    loadMock.mockResolvedValue({ status: "success", sessions: [current] });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SessionsPage
          csrfToken="csrf-token"
          initialSessions={[current, other]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("Текущая")).toBeInTheDocument();
    expect(screen.getByText("Safari · iPhone")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Завершить" }));
    expect(
      screen.getByRole("heading", { name: "Завершить сессии?" }),
    ).toBeInTheDocument();
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Завершить",
      }),
    );

    expect(revokeMock).toHaveBeenCalledWith(other.id, "csrf-token");
    expect(await screen.findByText("Сессия завершена.")).toBeInTheDocument();
    expect(screen.queryByText("Safari · iPhone")).not.toBeInTheDocument();
  });

  it("shows an explicit empty state", () => {
    render(
      <MemoryRouter>
        <SessionsPage csrfToken="csrf-token" initialSessions={[]} />
      </MemoryRouter>,
    );

    expect(screen.getByText("Активные сессии не найдены")).toBeInTheDocument();
  });

  it("confirms and revokes all other sessions", async () => {
    revokeOthersMock.mockResolvedValue({ status: "success", revokedCount: 1 });
    loadMock.mockResolvedValue({ status: "success", sessions: [current] });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SessionsPage
          csrfToken="csrf-token"
          initialSessions={[current, other]}
        />
      </MemoryRouter>,
    );

    await user.click(
      screen.getByRole("button", { name: "Завершить остальные" }),
    );
    await user.click(
      within(screen.getByRole("dialog")).getByRole("button", {
        name: "Завершить",
      }),
    );

    expect(revokeOthersMock).toHaveBeenCalledWith("csrf-token");
    expect(
      await screen.findByText("Остальные сессии завершены."),
    ).toBeInTheDocument();
  });
});
