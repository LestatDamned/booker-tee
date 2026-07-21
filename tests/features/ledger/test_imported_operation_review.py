from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm.exc import StaleDataError

from app.features.ledger.application.imported_operations import (
    ImportedOperationReviewUseCase,
    UpdateImportedOperationReviewFieldsCommand,
)
from app.features.ledger.domain.types import (
    OperationSource,
    OperationStatus,
    imported_operation_actions,
)
from app.features.ledger.errors import (
    ImportedOperationNotEditableError,
    OperationVersionConflictError,
)


@pytest.mark.parametrize(
    ("status", "can_edit"),
    [
        (OperationStatus.CONFIRMED, True),
        (OperationStatus.DRAFT, False),
        (OperationStatus.NEEDS_REVIEW, False),
        (OperationStatus.IGNORED, False),
        (OperationStatus.DUPLICATE, False),
    ],
)
def test_imported_operation_review_policy_only_edits_confirmed_operations(
    status: OperationStatus,
    can_edit: bool,
) -> None:
    assert imported_operation_actions(status).can_edit_review_fields is can_edit


@pytest.mark.asyncio
async def test_imported_review_rejects_stale_form_before_resolving_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation = imported_operation(status=OperationStatus.CONFIRMED, version=2)
    session = SessionStub()
    references = ReferenceResolverStub()
    use_case = build_use_case(monkeypatch, session, operation, references)

    with pytest.raises(OperationVersionConflictError):
        await use_case.update_review_fields(
            context=workspace_context(operation.workspace_id),
            command=review_command(operation.id, expected_version=1),
        )

    assert references.calls == []
    assert operation.description == "Old"
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_imported_review_rejects_ignored_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation = imported_operation(status=OperationStatus.IGNORED, version=3)
    session = SessionStub()
    references = ReferenceResolverStub()
    use_case = build_use_case(monkeypatch, session, operation, references)

    with pytest.raises(ImportedOperationNotEditableError):
        await use_case.update_review_fields(
            context=workspace_context(operation.workspace_id),
            command=review_command(operation.id, expected_version=3),
        )

    assert references.calls == []
    assert operation.description == "Old"
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_imported_review_maps_sqlalchemy_stale_write_to_version_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation = imported_operation(status=OperationStatus.CONFIRMED, version=4)
    session = SessionStub(stale_on_flush=True)
    use_case = build_use_case(
        monkeypatch,
        session,
        operation,
        ReferenceResolverStub(),
    )

    with pytest.raises(OperationVersionConflictError):
        await use_case.update_review_fields(
            context=workspace_context(operation.workspace_id),
            command=review_command(operation.id, expected_version=4),
        )

    assert session.commits == 0
    assert session.rollbacks == 1


class SessionStub:
    def __init__(self, *, stale_on_flush: bool = False) -> None:
        self.stale_on_flush = stale_on_flush
        self.commits = 0
        self.rollbacks = 0

    async def flush(self) -> None:
        if self.stale_on_flush:
            raise StaleDataError("stale imported operation")

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class ReferenceResolverStub:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_category_or_uncategorized(self, *args: object) -> object:
        self.calls.append("category")
        return SimpleNamespace(id=uuid4())

    async def get_property(self, *args: object) -> None:
        self.calls.append("property")
        return None


def build_use_case(
    monkeypatch: pytest.MonkeyPatch,
    session: SessionStub,
    operation: object,
    references: ReferenceResolverStub,
) -> ImportedOperationReviewUseCase:
    class RepositoryStub:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(self, *args: object) -> object:
            return operation

    monkeypatch.setattr(
        "app.features.ledger.application.imported_operations.LedgerRepository",
        RepositoryStub,
    )
    monkeypatch.setattr(
        "app.features.ledger.application.imported_operations.LedgerReferenceResolver",
        lambda _session: references,
    )
    return ImportedOperationReviewUseCase(cast(Any, session))


def imported_operation(*, status: OperationStatus, version: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=uuid4(),
        source=OperationSource.BANK_PDF,
        status=status,
        version=version,
        category_id=None,
        property_id=None,
        description="Old",
        updated_by_user_id=None,
    )


def review_command(
    operation_id: UUID,
    *,
    expected_version: int,
) -> UpdateImportedOperationReviewFieldsCommand:
    return UpdateImportedOperationReviewFieldsCommand(
        operation_id=operation_id,
        expected_version=expected_version,
        category_id=None,
        property_id=None,
        description="New",
    )


def workspace_context(workspace_id: UUID) -> Any:
    return cast(
        Any,
        SimpleNamespace(
            workspace=SimpleNamespace(id=workspace_id),
            user=SimpleNamespace(id=uuid4()),
        ),
    )
