from enum import StrEnum


class UploadedDocumentSource(StrEnum):
    WEB_UPLOAD = "web_upload"
    SYSTEM = "system"


class UploadedDocumentType(StrEnum):
    BANK_STATEMENT = "bank_statement"
    OTHER = "other"


class ParseAttemptStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    REQUIRES_REVIEW = "requires_review"
    FAILED = "failed"


class UploadedDocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PENDING_PARSE = "pending_parse"
    PARSING = "parsing"
    PARSED = "parsed"
    REQUIRES_REVIEW = "requires_review"
    FAILED_TO_PARSE = "failed_to_parse"
    IMPORTED = "imported"
    IGNORED = "ignored"
