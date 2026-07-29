class UnknownStatementMappingError(ValueError):
    pass


class MappingImportNotFoundError(UnknownStatementMappingError):
    pass


class MappingImportUnavailableError(UnknownStatementMappingError):
    pass


class MappingImportIdempotencyConflictError(UnknownStatementMappingError):
    pass
