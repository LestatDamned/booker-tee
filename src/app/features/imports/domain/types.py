from enum import StrEnum


class UploadedDocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PENDING_PARSE = "pending_parse"
    PARSING = "parsing"
    PARSED = "parsed"
    REQUIRES_REVIEW = "requires_review"
    FAILED_TO_PARSE = "failed_to_parse"
    IMPORTED = "imported"
    IGNORED = "ignored"


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
