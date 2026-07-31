import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ToastViewport, useToastQueue } from "./toast";

afterEach(() => {
  vi.useRealTimers();
});

describe("toast", () => {
  it("announces queued messages without moving focus", async () => {
    const user = userEvent.setup();
    render(<ToastHarness messages={["Счёт создан", "Счёт восстановлен"]} />);

    const first = screen.getByRole("status");
    expect(first).toHaveTextContent("Счёт создан");
    expect(first).toHaveAttribute("aria-atomic", "true");

    await user.click(
      screen.getByRole("button", { name: "Закрыть уведомление" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent("Счёт восстановлен");
  });

  it("dismisses a non-interactive success message after six seconds", () => {
    vi.useFakeTimers();
    render(<ToastHarness messages={["Изменения сохранены"]} />);

    expect(screen.getByRole("status")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(6000));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});

function ToastHarness({ messages }: { messages: string[] }) {
  const { dismissToast, showToast, toast } = useToastQueue();

  useEffect(() => {
    for (const message of messages) showToast({ message });
  }, [messages, showToast]);

  return (
    <>
      <button type="button">Текущий фокус</button>
      <ToastViewport onDismiss={dismissToast} toast={toast} />
    </>
  );
}
