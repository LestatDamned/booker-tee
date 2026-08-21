class WorkspaceTestSession:
    def __init__(self) -> None:
        self.commit_count = 0
        self.flush_count = 0
        self.rollback_count = 0

    async def commit(self) -> None:
        self.commit_count += 1

    async def flush(self) -> None:
        self.flush_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1
