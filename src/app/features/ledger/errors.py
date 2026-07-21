class LedgerPostingError(ValueError):
    pass


class AccountUnavailableError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Account is not available in this workspace.")


class CategoryUnavailableError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Category is not available in this workspace.")


class PropertyUnavailableError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Property is not available in this workspace.")


class InvalidAmountError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Amount must be positive.")


class SameTransferAccountError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Transfer accounts must be different.")


class TransferCurrencyMismatchError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Cross-currency transfers are not supported in the MVP.")


class ManualOperationNotFoundError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Manual operation was not found.")


class OperationIdempotencyConflictError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Idempotency key was reused with a different manual operation.")


class OperationVersionConflictError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Operation changed after this edit form was loaded.")


class ManualOperationLifecycleConflictError(LedgerPostingError):
    pass


class ManualOperationNotEditableError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Only confirmed or draft manual operations can be edited.")


class ImportedOperationNotFoundError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Imported operation was not found.")


class ImportedOperationNotEditableError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Only confirmed imported operations can be edited.")
