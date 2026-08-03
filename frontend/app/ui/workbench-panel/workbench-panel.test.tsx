import { useRef, useState } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { WorkbenchPanel } from "./workbench-panel";

describe("WorkbenchPanel", () => {
  it("labels the dialog and restores focus after closing", async () => {
    const user = userEvent.setup();
    render(<PanelHarness />);

    const trigger = screen.getByRole("button", { name: "Открыть" });
    await user.click(trigger);

    expect(screen.getByRole("dialog")).toHaveAccessibleName("Новая операция");
    await waitFor(() =>
      expect(screen.getByRole("textbox", { name: "Описание" })).toHaveFocus(),
    );
    await user.click(screen.getByRole("button", { name: "Закрыть" }));

    await waitFor(() => expect(trigger).toHaveFocus());
  });
});

function PanelHarness() {
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <button onClick={() => setOpen(true)}>Открыть</button>
      {open ? (
        <WorkbenchPanel
          initialFocusRef={inputRef}
          onClose={() => setOpen(false)}
          title="Новая операция"
        >
          <input ref={inputRef} aria-label="Описание" />
        </WorkbenchPanel>
      ) : null}
    </>
  );
}
