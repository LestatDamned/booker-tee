import { afterEach, describe, expect, it, vi } from "vitest";

import { focusNextReviewItem } from "./focus-next-review-item";
import { importReviewPayload, remainingItemId } from "./test-support";

describe("focus next review item", () => {
  afterEach(() => {
    vi.useRealTimers();
    document.body.replaceChildren();
  });

  it("moves focus to the server-owned first remaining row after reconciliation", () => {
    vi.useFakeTimers();
    const review = importReviewPayload();
    const row = document.createElement("article");
    row.id = `raw-${remainingItemId}`;
    row.tabIndex = -1;
    document.body.append(row);

    focusNextReviewItem(review);
    vi.runAllTimers();

    expect(row).toHaveFocus();
  });

  it("leaves focus unchanged when the queue is complete", () => {
    vi.useFakeTimers();
    const review = importReviewPayload();
    review.queue.firstRemainingItemId = null;
    const control = document.createElement("button");
    document.body.append(control);
    control.focus();

    focusNextReviewItem(review);
    vi.runAllTimers();

    expect(control).toHaveFocus();
  });
});
