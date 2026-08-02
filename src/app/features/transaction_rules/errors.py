from dataclasses import dataclass


class TransactionRuleError(ValueError):
    pass


class TransactionRuleNotFoundError(TransactionRuleError):
    pass


class TransactionRuleValidationError(TransactionRuleError):
    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class TransactionRuleCreateReplayConflictError(TransactionRuleError):
    pass


class TransactionRuleUpdateConflictError(TransactionRuleError):
    pass


class TransactionRuleLifecycleConflictError(TransactionRuleError):
    pass


class TransactionRuleActivationBlockedError(TransactionRuleValidationError):
    pass


@dataclass(frozen=True)
class TransactionRuleDeleteDependencies:
    is_active: bool = False
    raw_suggestion_count: int = 0

    @property
    def has_blockers(self) -> bool:
        return self.is_active or self.raw_suggestion_count > 0


class TransactionRuleDeleteBlockedError(TransactionRuleError):
    def __init__(self, dependencies: TransactionRuleDeleteDependencies) -> None:
        message = (
            "Сначала выключите правило."
            if dependencies.is_active
            else "Правило используется в истории импорта и не может быть удалено."
        )
        super().__init__(message)
        self.dependencies = dependencies
