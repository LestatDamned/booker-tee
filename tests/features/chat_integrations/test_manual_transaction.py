from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.features.chat_integrations.actions.manual import ChatManualConfirmationSelection
from app.features.chat_integrations.errors import ChatManualOperationError
from app.features.chat_integrations.use_cases.manual import operations as manual_operations
from app.features.chat_integrations.use_cases.manual.dto import ChatManualOperationConfirmation
from app.features.chat_integrations.use_cases.manual.posting import ChatManualOperationPoster
from app.features.chat_integrations.use_cases.manual.state_store import (
    ChatManualOperationStateStore,
)
from app.features.ledger.application.manual_mutations import ManualOperationCreateOutcome
from app.features.ledger.domain.types import OperationType


class SessionStub:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class StateStoreStub:
    def __init__(self, *, fail_consume: bool = False) -> None:
        self.state = SimpleNamespace(step="confirm", state_payload={})
        self.fail_consume = fail_consume
        self.consumed = False

    async def get_by_token(self, **_kwargs: object) -> object:
        return self.state

    async def consume(self, _state: object) -> None:
        if self.fail_consume:
            raise RuntimeError("state consume failed")
        self.consumed = True


class OperationPosterStub:
    async def post(self, **_kwargs: object) -> object:
        return SimpleNamespace(id=uuid4())


@pytest.mark.parametrize("replayed", [True, False])
async def test_chat_manual_poster_records_only_new_operations(replayed: bool) -> None:
    operation = SimpleNamespace(
        id=uuid4(),
        type=OperationType.INCOME,
        description="Доход",
    )
    manual_writer = SimpleNamespace(
        create_income_expense=AsyncMock(
            return_value=ManualOperationCreateOutcome(
                operation=cast(Any, operation),
                replayed=replayed,
            )
        )
    )
    activity = SimpleNamespace(manual_operation_created=AsyncMock())
    poster = ChatManualOperationPoster(cast(Any, manual_writer), cast(Any, activity))

    result = await poster.post(
        context=cast(
            Any,
            SimpleNamespace(
                workspace=SimpleNamespace(id=uuid4()),
                user=SimpleNamespace(id=uuid4()),
            ),
        ),
        payload={"account_id": str(uuid4())},
        confirmation=confirmation(),
    )

    assert result is operation
    assert activity.manual_operation_created.await_count == (0 if replayed else 1)


async def test_chat_manual_confirmation_commits_operation_and_state_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionStub()
    service = manual_operations.ChatManualOperationService(cast(Any, session))
    states = StateStoreStub()
    service.states = cast(Any, states)
    service.operation_poster = cast(Any, OperationPosterStub())
    monkeypatch.setattr(
        manual_operations.ChatManualOperationStateReader,
        "read_confirmation",
        staticmethod(lambda *_args, **_kwargs: confirmation()),
    )

    await service.confirm(
        context=cast(Any, SimpleNamespace()),
        selection=ChatManualConfirmationSelection(action_token="token"),
    )

    assert states.consumed is True
    assert session.commits == 1
    assert session.rollbacks == 0


async def test_chat_manual_confirmation_rolls_back_when_state_cannot_be_consumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = SessionStub()
    service = manual_operations.ChatManualOperationService(cast(Any, session))
    service.states = cast(Any, StateStoreStub(fail_consume=True))
    service.operation_poster = cast(Any, OperationPosterStub())
    monkeypatch.setattr(
        manual_operations.ChatManualOperationStateReader,
        "read_confirmation",
        staticmethod(lambda *_args, **_kwargs: confirmation()),
    )

    with pytest.raises(RuntimeError, match="state consume failed"):
        await service.confirm(
            context=cast(Any, SimpleNamespace()),
            selection=ChatManualConfirmationSelection(action_token="token"),
        )

    assert session.commits == 0
    assert session.rollbacks == 1


def confirmation() -> ChatManualOperationConfirmation:
    return ChatManualOperationConfirmation(
        action_token="token",
        operation_type=OperationType.INCOME,
        amount=Decimal("100.00"),
        currency="RUB",
        operation_date=date(2026, 7, 21),
        account_name="Карта",
        description="Доход",
    )


async def test_manual_state_consume_rejects_an_already_claimed_action() -> None:
    class ClaimedStateRepository:
        async def try_consume_active_conversation_state(
            self,
            _state: object,
            **_kwargs: object,
        ) -> bool:
            return False

    store = ChatManualOperationStateStore(cast(Any, object()))
    store.chat_integrations = cast(Any, ClaimedStateRepository())

    with pytest.raises(ChatManualOperationError, match="устарело"):
        await store.consume(cast(Any, SimpleNamespace()))
