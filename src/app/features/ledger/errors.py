class LedgerPostingError(ValueError):
    pass


class ManualOperationNotFoundError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Manual operation was not found.")


class OperationIdempotencyConflictError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Idempotency key was reused with a different manual operation.")


class OperationVersionConflictError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Manual operation changed after this edit form was loaded.")


class ManualOperationLifecycleConflictError(LedgerPostingError):
    pass
