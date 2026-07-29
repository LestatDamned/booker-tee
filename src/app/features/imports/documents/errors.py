class UploadValidationError(ValueError):
    pass


class UploadAccountNotFoundError(UploadValidationError):
    pass


class UploadIdempotencyConflictError(UploadValidationError):
    pass


class UploadTooLargeError(UploadValidationError):
    pass


class ImportDocumentManagementError(ValueError):
    pass
