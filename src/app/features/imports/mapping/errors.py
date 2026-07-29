from dataclasses import dataclass

from app.features.imports.mapping.dto import MappingBlockingReasonCode


class UnknownStatementMappingError(ValueError):
    pass


class MappingImportNotFoundError(UnknownStatementMappingError):
    pass


class MappingImportUnavailableError(UnknownStatementMappingError):
    pass


class MappingImportIdempotencyConflictError(UnknownStatementMappingError):
    pass


@dataclass(frozen=True)
class StatementMappingUnavailableError(Exception):
    reason_codes: tuple[MappingBlockingReasonCode, ...]

    def __str__(self) -> str:
        return "Настройка колонок недоступна для текущего состояния документа."
