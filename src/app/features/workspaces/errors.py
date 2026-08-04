class WorkspaceError(ValueError):
    pass


class WorkspaceNotFoundError(WorkspaceError):
    pass


class WorkspaceSwitchConflictError(WorkspaceError):
    def __init__(self, *, current_workspace_id: object) -> None:
        super().__init__("Текущий workspace уже изменился в другой вкладке.")
        self.current_workspace_id = current_workspace_id


class WorkspaceIdempotencyConflictError(WorkspaceError):
    pass


class WorkspaceSessionNotFoundError(WorkspaceError):
    pass


class WorkspaceSettingsForbiddenError(WorkspaceError):
    pass


class WorkspaceUpdateConflictError(WorkspaceError):
    pass


class WorkspaceMemberConflictError(WorkspaceError):
    pass


class WorkspaceMemberTransitionError(WorkspaceError):
    def __init__(self, message: str, *, reason_codes: list[str]) -> None:
        super().__init__(message)
        self.reason_codes = reason_codes


class WorkspaceOwnershipTransferConflictError(WorkspaceError):
    pass


class WorkspaceInvitationConflictError(WorkspaceError):
    pass


class WorkspaceInvitationNotFoundError(WorkspaceError):
    pass


class WorkspaceInvitationTransitionError(WorkspaceError):
    def __init__(self, message: str, *, reason_codes: list[str]) -> None:
        super().__init__(message)
        self.reason_codes = reason_codes


class WorkspaceLifecycleConflictError(WorkspaceError):
    pass


class WorkspaceLifecycleTransitionError(WorkspaceError):
    def __init__(self, message: str, *, reason_codes: list[str]) -> None:
        super().__init__(message)
        self.reason_codes = reason_codes
