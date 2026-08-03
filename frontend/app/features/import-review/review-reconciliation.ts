import type { ImportReviewDto } from "./api/import-review-api";

export function reviewForDocument(
  reviews: ImportReviewDto[],
  documentId: string,
): ImportReviewDto | undefined {
  return reviews.find((review) => review.document.id === documentId);
}
