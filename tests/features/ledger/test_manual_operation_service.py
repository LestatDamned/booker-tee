from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

import app.features.ledger.application.manual_operations as service_module
from app.features.ledger.application.manual_mutations import ManualOperationCreateOutcome
from app.features.ledger.application.manual_operations import ManualOperationService
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.schemas.manual import (
    CreateManualIncomeExpenseCommand,
    ManualOperationReadDto,
)
from app.features.workspaces.service import WorkspaceContext


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(None, id="missing"),
        pytest.param(OperationSource.BANK_PDF, id="bank-pdf"),
        pytest.param(OperationSource.DEBT, id="debt"),
        pytest.param(OperationSource.SYSTEM, id="system"),
    ],
)
async def test_get_hides_missing_and_non_manual_operations(
    source: OperationSource | None,
) -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    operation = None if source is None else SimpleNamespace(id=operation_id, source=source)
    lookup = AsyncMock(return_value=operation)
    service = ManualOperationService(cast(Any, object()))
    service._ledger = cast(
        Any,
        SimpleNamespace(get_operation_for_workspace=lookup),
    )

    result = await service.get(
        workspace_id=workspace_id,
        operation_id=operation_id,
    )

    assert result is None
    lookup.assert_awaited_once_with(workspace_id, operation_id)


async def test_create_returns_reloaded_read_dto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    persisted_operation = SimpleNamespace(
        id=operation_id,
        source=OperationSource.MANUAL,
        type=OperationType.INCOME,
        description="Доход",
    )
    expected = manual_operation_dto(operation_id)

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(
            self,
            requested_workspace_id: UUID,
            requested_operation_id: UUID,
        ) -> object:
            assert requested_workspace_id == workspace_id
            assert requested_operation_id == operation_id
            return persisted_operation

    class FakeUseCase:
        def __init__(self, _session: object) -> None:
            pass

        async def create_income_expense(self, **_kwargs: object) -> object:
            return ManualOperationCreateOutcome(
                operation=cast(Any, persisted_operation),
                replayed=False,
            )

    monkeypatch.setattr(service_module, "LedgerRepository", FakeRepository)
    monkeypatch.setattr(service_module, "ManualOperationWriter", FakeUseCase)
    monkeypatch.setattr(
        service_module.ManualOperationReadMapper,
        "from_operation",
        staticmethod(lambda _operation: expected),
    )
    session = SimpleNamespace(commits=0, rollbacks=0)

    async def commit() -> None:
        session.commits += 1

    async def rollback() -> None:
        session.rollbacks += 1

    session.commit = commit
    session.rollback = rollback
    service = ManualOperationService(cast(Any, session))
    service._activity = cast(Any, SimpleNamespace(manual_operation_created=AsyncMock()))
    context = cast(
        WorkspaceContext,
        SimpleNamespace(
            workspace=SimpleNamespace(id=workspace_id),
            user=SimpleNamespace(id=uuid4()),
        ),
    )

    result = await service.create(
        context=context,
        command=manual_income_command(),
    )

    assert result is expected
    service._activity.manual_operation_created.assert_awaited_once()
    assert session.commits == 1
    assert session.rollbacks == 0


@pytest.mark.parametrize(
    "replayed",
    [
        pytest.param(True, id="replay-skips-activity"),
        pytest.param(False, id="activity-failure-rolls-back"),
    ],
)
async def test_create_activity_is_idempotent_and_transactional(
    monkeypatch: pytest.MonkeyPatch,
    replayed: bool,
) -> None:
    workspace_id = uuid4()
    operation = SimpleNamespace(
        id=uuid4(),
        source=OperationSource.MANUAL,
        type=OperationType.INCOME,
        description="Доход",
    )

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(
            self,
            _workspace_id: UUID,
            _operation_id: UUID,
        ) -> object:
            return operation

    class FakeUseCase:
        def __init__(self, _session: object) -> None:
            pass

        async def create_income_expense(self, **_kwargs: object) -> object:
            return ManualOperationCreateOutcome(
                operation=cast(Any, operation),
                replayed=replayed,
            )

    monkeypatch.setattr(service_module, "LedgerRepository", FakeRepository)
    monkeypatch.setattr(service_module, "ManualOperationWriter", FakeUseCase)
    monkeypatch.setattr(
        service_module.ManualOperationReadMapper,
        "from_operation",
        staticmethod(lambda _operation: manual_operation_dto(operation.id)),
    )
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    service = ManualOperationService(cast(Any, session))
    activity = AsyncMock(side_effect=RuntimeError("activity failed"))
    service._activity = cast(Any, SimpleNamespace(manual_operation_created=activity))
    context = cast(
        WorkspaceContext,
        SimpleNamespace(
            workspace=SimpleNamespace(id=workspace_id),
            user=SimpleNamespace(id=uuid4()),
        ),
    )
    command = manual_income_command()

    if replayed:
        await service.create(context=context, command=command)
        activity.assert_not_awaited()
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
    else:
        with pytest.raises(RuntimeError, match="activity failed"):
            await service.create(context=context, command=command)
        activity.assert_awaited_once()
        session.commit.assert_not_awaited()
        session.rollback.assert_awaited_once()


async def test_create_rolls_back_when_writer_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

    class FailingWriter:
        def __init__(self, _session: object) -> None:
            pass

        async def create_income_expense(self, **_kwargs: object) -> object:
            raise RuntimeError("write failed")

    monkeypatch.setattr(service_module, "LedgerRepository", FakeRepository)
    monkeypatch.setattr(service_module, "ManualOperationWriter", FailingWriter)
    session = SimpleNamespace(commits=0, rollbacks=0)

    async def commit() -> None:
        session.commits += 1

    async def rollback() -> None:
        session.rollbacks += 1

    session.commit = commit
    session.rollback = rollback
    service = ManualOperationService(cast(Any, session))

    with pytest.raises(RuntimeError, match="write failed"):
        await service.create(
            context=cast(
                WorkspaceContext,
                SimpleNamespace(workspace=SimpleNamespace(id=uuid4())),
            ),
            command=manual_income_command(),
        )

    assert session.commits == 0
    assert session.rollbacks == 1


def manual_operation_dto(operation_id: UUID) -> ManualOperationReadDto:
    return ManualOperationReadDto(
        id=operation_id,
        version=1,
        operation_type=OperationType.INCOME,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 7, 21),
        description="Доход",
        money=None,
        account=None,
        source_account=None,
        destination_account=None,
        category=None,
        property=None,
    )


def manual_income_command() -> CreateManualIncomeExpenseCommand:
    return CreateManualIncomeExpenseCommand(
        operation_type=OperationType.INCOME,
        account_id=uuid4(),
        amount=Decimal("10.00"),
        operation_date=date(2026, 7, 21),
        description="Доход",
        category_id=None,
        property_id=None,
        idempotency_key=uuid4(),
    )
