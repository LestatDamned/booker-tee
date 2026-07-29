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
