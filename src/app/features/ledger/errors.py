class LedgerPostingError(ValueError):
    pass


class OperationVersionConflictError(LedgerPostingError):
    def __init__(self) -> None:
        super().__init__("Manual operation changed after this edit form was loaded.")
