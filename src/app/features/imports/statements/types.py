from enum import StrEnum


class RawTransactionStatus(StrEnum):
    EXTRACTED = "extracted"
    NORMALIZED = "normalized"
    SUGGESTED = "suggested"
    NEEDS_REVIEW = "needs_review"
    MATCHED = "matched"
    IGNORED = "ignored"
    DUPLICATE = "duplicate"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    FAILED = "failed"
    CONFIRMED = "confirmed"
