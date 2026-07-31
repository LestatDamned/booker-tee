import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { FoundationGallery } from "./foundation-gallery";

describe("FoundationGallery", () => {
  it("keeps theme interactions independent and restores disclosure focus", async () => {
    render(
      <MemoryRouter>
        <FoundationGallery />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("navigation", {
        name: "Примеры состояний маршрутов",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Загрузка" })).toHaveAttribute(
      "href",
      "/app/foundation?route-state=loading",
    );
    expect(screen.getByRole("link", { name: "Ошибка" })).toHaveAttribute(
      "href",
      "/app/foundation?route-state=error",
    );

    const editButtons = screen.getAllByRole("button", {
      name: "Редактировать",
    });
    const closeButtons = screen.getAllByRole("button", {
      name: "Закрыть панель",
    });
    const [firstEditButton, secondEditButton, thirdEditButton] = editButtons;
    const [firstCloseButton] = closeButtons;
    if (
      !firstEditButton ||
      !secondEditButton ||
      !thirdEditButton ||
      !firstCloseButton
    ) {
      throw new Error("All theme fixtures must render their panel controls.");
    }

    fireEvent.click(firstCloseButton);

    await waitFor(() => expect(firstEditButton).toHaveFocus());
    expect(firstEditButton).toHaveAttribute("aria-expanded", "false");
    expect(secondEditButton).toHaveAttribute("aria-expanded", "true");
    expect(thirdEditButton).toHaveAttribute("aria-expanded", "true");
  });
});
