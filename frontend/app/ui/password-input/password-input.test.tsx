import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PasswordInput } from "./password-input";

describe("PasswordInput", () => {
  it("toggles visibility without submitting the form", () => {
    render(<PasswordInput aria-label="Пароль" id="password" />);

    const input = screen.getByLabelText("Пароль");
    const toggle = screen.getByRole("button", { name: "Показать" });

    expect(input).toHaveAttribute("type", "password");
    expect(toggle).toHaveAttribute("type", "button");
    expect(toggle).toHaveAttribute("aria-controls", "password");

    fireEvent.click(toggle);

    expect(input).toHaveAttribute("type", "text");
    expect(toggle).toHaveTextContent("Скрыть");
    expect(toggle).toHaveAttribute("aria-pressed", "true");
  });

  it("disables the visibility control with the input", () => {
    render(<PasswordInput aria-label="Пароль" disabled id="password" />);

    expect(screen.getByLabelText("Пароль")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Показать" })).toBeDisabled();
  });
});
