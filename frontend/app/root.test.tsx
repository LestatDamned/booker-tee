import { afterEach, expect, it, vi } from "vitest";

import { navigateToHashTarget } from "./root";

afterEach(() => {
  vi.useRealTimers();
});

it("scrolls and focuses a rendered hash target", () => {
  vi.useFakeTimers();
  const target = document.createElement("article");
  target.id = "operation-123";
  target.tabIndex = -1;
  target.scrollIntoView = vi.fn();
  document.body.append(target);

  expect(navigateToHashTarget("#operation-123")).toBe(true);
  expect(target.scrollIntoView).toHaveBeenCalledWith({ block: "center" });
  expect(target).toHaveFocus();
  expect(target).toHaveAttribute("data-hash-target-arrival");

  vi.advanceTimersByTime(4_000);
  expect(target).not.toHaveAttribute("data-hash-target-arrival");
  expect(target).toHaveAttribute("data-hash-target-focus");
});
