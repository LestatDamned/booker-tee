import type { ImportReviewDto } from "./api/import-review-api";

export function focusNextReviewItem(review: ImportReviewDto) {
  if (!review.queue.firstRemainingItemId) return;
  window.setTimeout(() => {
    document
      .getElementById(`raw-${review.queue.firstRemainingItemId}`)
      ?.focus();
  });
}
