from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from ledger_test_support import workspace_context
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
    LedgerPostingError,
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


@pytest.mark.parametrize(
    ("status", "version", "expected_version", "expected_error"),
    [
        pytest.param(
            OperationStatus.CONFIRMED,
            2,
            1,
            OperationVersionConflictError,
            id="stale-version",
        ),
        pytest.param(
            OperationStatus.IGNORED,
            3,
            3,
            ImportedOperationNotEditableError,
            id="ignored-status",
        ),
    ],
)
async def test_imported_review_rejects_invalid_state_or_version_before_references(
    monkeypatch: pytest.MonkeyPatch,
    status: OperationStatus,
    version: int,
    expected_version: int,
    expected_error: type[LedgerPostingError],
) -> None:
    operation = imported_operation(status=status, version=version)
    session = SessionStub()
    references = ReferenceResolverStub()
    use_case = build_use_case(monkeypatch, session, operation, references)

    with pytest.raises(expected_error):
        await use_case.update_review_fields(
            context=workspace_context(operation.workspace_id),
            command=review_command(operation.id, expected_version=expected_version),
        )

    assert references.calls == []
    assert operation.description == "Old"
    assert session.commits == 0
    assert session.rollbacks == 1


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


async def test_imported_review_changes_only_review_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation = imported_operation(status=OperationStatus.CONFIRMED, version=3)
    operation.type = "expense"
    operation.operation_date = date(2026, 6, 15)
    operation.money_entries = [SimpleNamespace(amount=Decimal("-120.00"))]
    operation.raw_transactions = [SimpleNamespace(id=uuid4())]
    category = SimpleNamespace(id=uuid4())
    property_ = SimpleNamespace(id=uuid4())
    references = ReferenceResolverStub(category=category, property_=property_)
    session = SessionStub()
    use_case = build_use_case(monkeypatch, session, operation, references)
    context = workspace_context(operation.workspace_id)

    updated = await use_case.update_review_fields(
        context=context,
        command=review_command(
            operation.id,
            expected_version=3,
            category_id=category.id,
            property_id=property_.id,
            description="  New   label  ",
        ),
    )

    assert updated is operation
    assert operation.category_id == category.id
    assert operation.property_id == property_.id
    assert operation.description == "New label"
    assert operation.updated_by_user_id == context.user.id
    assert operation.status is OperationStatus.CONFIRMED
    assert operation.type == "expense"
    assert operation.operation_date == date(2026, 6, 15)
    assert operation.money_entries[0].amount == Decimal("-120.00")
    assert len(operation.raw_transactions) == 1
    assert session.flushes == 1
    assert session.commits == 1
    assert session.rollbacks == 0
    cast(Any, use_case.activity.imported_operation_updated).assert_awaited_once()


async def test_imported_review_rejects_manual_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation = imported_operation(status=OperationStatus.CONFIRMED, version=1)
    operation.source = OperationSource.MANUAL
    session = SessionStub()
    references = ReferenceResolverStub()
    use_case = build_use_case(monkeypatch, session, operation, references)

    with pytest.raises(LedgerPostingError, match="Only imported bank PDF"):
        await use_case.update_review_fields(
            context=workspace_context(operation.workspace_id),
            command=review_command(operation.id, expected_version=1),
        )

    assert references.calls == []
    assert operation.description == "Old"
    assert session.flushes == 0
    assert session.commits == 0
    assert session.rollbacks == 1


class SessionStub:
    def __init__(self, *, stale_on_flush: bool = False) -> None:
        self.stale_on_flush = stale_on_flush
        self.flushes = 0
        self.commits = 0
        self.rollbacks = 0

    async def flush(self) -> None:
        if self.stale_on_flush:
            raise StaleDataError("stale imported operation")
        self.flushes += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class ReferenceResolverStub:
    def __init__(
        self,
        *,
        category: object | None = None,
        property_: object | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.category = category or SimpleNamespace(id=uuid4())
        self.property = property_

    async def get_category_or_uncategorized(self, *args: object) -> object:
        self.calls.append("category")
        return self.category

    async def get_property(self, *args: object) -> object | None:
        self.calls.append("property")
        return self.property


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
    use_case = ImportedOperationReviewUseCase(cast(Any, session))
    use_case.activity = cast(Any, SimpleNamespace(imported_operation_updated=AsyncMock()))
    return use_case


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
    category_id: UUID | None = None,
    property_id: UUID | None = None,
    description: str = "New",
) -> UpdateImportedOperationReviewFieldsCommand:
    return UpdateImportedOperationReviewFieldsCommand(
        operation_id=operation_id,
        expected_version=expected_version,
        category_id=category_id,
        property_id=property_id,
        description=description,
    )
