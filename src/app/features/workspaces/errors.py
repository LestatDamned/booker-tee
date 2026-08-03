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
