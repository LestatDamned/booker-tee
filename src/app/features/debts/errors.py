class DebtError(ValueError):
    pass


class DebtAccountUnavailableError(DebtError):
    pass


class DebtCurrencyMismatchError(DebtError):
    pass


class DebtIdempotencyConflictError(DebtError):
    pass


class DebtPaymentNotFoundError(DebtError):
    pass


class DebtPaymentConflictError(DebtError):
    pass


class DebtNotFoundError(DebtError):
    pass


class DebtLifecycleConflictError(DebtError):
    pass


class DebtMaintenanceConflictError(DebtError):
    pass


class DebtDeleteBlockedError(DebtError):
    pass
