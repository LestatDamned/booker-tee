class UploadValidationError(ValueError):
    pass


class UploadAccountNotFoundError(UploadValidationError):
    pass


class UploadIdempotencyConflictError(UploadValidationError):
    pass


class UploadTooLargeError(UploadValidationError):
    pass


class RawTransactionReviewError(ValueError):
    pass


class ImportReparseError(ValueError):
    pass


class ImportDocumentManagementError(ValueError):
    pass


class UnknownStatementMappingError(ValueError):
    pass


class MappingImportNotFoundError(UnknownStatementMappingError):
    pass


class MappingImportUnavailableError(UnknownStatementMappingError):
    pass


class MappingImportIdempotencyConflictError(UnknownStatementMappingError):
    pass
