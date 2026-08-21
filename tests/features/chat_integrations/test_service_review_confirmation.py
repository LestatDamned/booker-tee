from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.actions.review import (
    ChatReviewCategoryPageSelection,
    ChatReviewCategorySelection,
    ChatReviewPropertySelection,
    ChatReviewReturnSelection,
)
from app.features.chat_integrations.handlers import (
    review_confirmation as chat_review_confirmation_handler,
)
from app.features.chat_integrations.handlers import review_queue as chat_review_queue_handler
from app.features.chat_integrations.service import ChatEventService
from app.features.chat_integrations.use_cases.review import (
    dto as chat_review_dto,
)
from app.features.chat_integrations.use_cases.review.confirmation import (
    ChatReviewConfirmationService,
)
from app.features.imports.statements.types import RawTransactionStatus
from app.features.workspaces.service import WorkspaceContext

from .chat_test_support import bound_chat_workspace, callback_event, patch_bound_workspace


def _build_chat_review_queue_item(
    *,
    description: str = "NEXT ROW",
    document_id: UUID | None = None,
    raw_transaction_id: UUID | None = None,
) -> chat_review_dto.ChatReviewQueueItem:
    return chat_review_dto.ChatReviewQueueItem(
        document_id=document_id or uuid4(),
        raw_transaction_id=raw_transaction_id or uuid4(),
        row_index=2,
        status="needs_review",
        account_name="T-Bank Card",
        operation_date=date(2026, 6, 30),
        amount=Decimal("-500.00"),
        amount_raw=None,
        currency="RUB",
        description=description,
        suggested_operation_type="expense",
        normalization_error=None,
    )


def _patch_next_review_item_after_action(
    monkeypatch: pytest.MonkeyPatch,
    *,
    workspace_id: UUID,
    item: chat_review_dto.ChatReviewQueueItem | None = None,
) -> None:
    next_item = item or _build_chat_review_queue_item()

    class FakeChatReviewQueueService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_next_review_item(self, context: WorkspaceContext):
            assert context.workspace.id == workspace_id
            return chat_review_dto.StartedChatReviewItem(
                action_token="nexttoken",
                item=next_item,
            )

    monkeypatch.setattr(
        chat_review_queue_handler, "ChatReviewQueueService", FakeChatReviewQueueService
    )


async def test_chat_confirmation_claims_action_and_applies_shared_actor_before_commit() -> None:
    events: list[str] = []
    commands: list[object] = []
    state_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    category_id = uuid4()
    property_id = uuid4()
    state = SimpleNamespace(
        id=state_id,
        step="choose_property",
        state_payload={
            "document_id": str(document_id),
            "raw_transaction_id": str(raw_transaction_id),
            "category_id": str(category_id),
            "category_name": "Продукты",
            "property_ids": [str(property_id)],
            "offer_rule_suggestion": False,
        },
    )
    item = _build_chat_review_queue_item(
        document_id=document_id,
        raw_transaction_id=raw_transaction_id,
    )

    class SessionStub:
        async def commit(self) -> None:
            events.append("commit")

        async def rollback(self) -> None:
            events.append("rollback")

    class ChatIntegrationsStub:
        async def get_active_conversation_state(self, **_kwargs: object) -> object:
            return state

        async def try_consume_active_conversation_state(
            self,
            _state: object,
            **_kwargs: object,
        ) -> bool:
            events.append("claim")
            return True

    class ReviewQueueStub:
        async def read_item(self, **_kwargs: object) -> object:
            return item

    class ConfirmationActorStub:
        async def apply(self, **kwargs: object) -> None:
            events.append("apply")
            commands.append(kwargs["command"])

    session = SessionStub()
    service = ChatReviewConfirmationService(
        cast(AsyncSession, session),
        Settings(public_base_url="https://booker.example"),
    )
    service.chat_integrations = cast(Any, ChatIntegrationsStub())
    service.review_queue = cast(Any, ReviewQueueStub())
    service.confirmations = cast(Any, ConfirmationActorStub())

    result = await service.confirm_with_property(
        context=WorkspaceContext(
            user=cast(Any, SimpleNamespace(id=uuid4())),
            workspace=cast(Any, SimpleNamespace(id=uuid4())),
            membership=cast(Any, SimpleNamespace(id=uuid4())),
        ),
        selection=ChatReviewPropertySelection(
            action_token="propertytoken",
            property_index=0,
        ),
    )

    command = cast(Any, commands[0])
    assert events == ["claim", "apply", "commit"]
    assert command.document_id == document_id
    assert command.item_id == raw_transaction_id
    assert command.operation_type is None
    assert command.expected_status is RawTransactionStatus.NEEDS_REVIEW
    assert command.idempotency_key == state_id
    assert result.action_result is not None
    assert result.action_result.action_label == "операция подтверждена"


async def test_chat_event_service_starts_review_confirmation_category_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    category_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def start_category_selection(
            self,
            *,
            context: WorkspaceContext,
            action_token: str,
        ):
            assert context.workspace.id == workspace_id
            assert action_token == "reviewtoken"
            return chat_review_dto.StartedChatReviewCategorySelection(
                action_token="categorytoken",
                item=chat_review_dto.ChatReviewQueueItem(
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    row_index=0,
                    status="needs_review",
                    account_name="T-Bank Card",
                    operation_date=date(2026, 6, 30),
                    amount=Decimal("-1250.00"),
                    amount_raw=None,
                    currency="RUB",
                    description="MAGNIT",
                    suggested_operation_type="expense",
                    normalization_error=None,
                ),
                category_choices=(
                    chat_review_dto.ChatReviewCategoryChoice(
                        id=category_id,
                        name="Продукты",
                    ),
                ),
            )

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_review_confirmation_handler,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )

    event = callback_event("rev:reviewtoken:conf")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Выбери категорию" in response.text
    assert "📝 Описание: MAGNIT" in response.text
    assert response.buttons[0][0].text == "Продукты"
    assert response.buttons[0][0].callback_data == "rvc:categorytoken:0"
    assert response.buttons[1][0].text == "🔎 К строке"
    assert response.buttons[1][0].callback_data == "rvb:categorytoken"


async def test_chat_event_service_changes_review_category_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def change_category_page(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewCategoryPageSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "categorytoken"
            assert selection.page_index == 1
            return chat_review_dto.StartedChatReviewCategorySelection(
                action_token="categorytoken",
                item=chat_review_dto.ChatReviewQueueItem(
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    row_index=0,
                    status="needs_review",
                    account_name="T-Bank Card",
                    operation_date=date(2026, 6, 30),
                    amount=Decimal("-1250.00"),
                    amount_raw=None,
                    currency="RUB",
                    description="MAGNIT",
                    suggested_operation_type="expense",
                    normalization_error=None,
                ),
                category_choices=(
                    chat_review_dto.ChatReviewCategoryChoice(
                        id=uuid4(),
                        name="Транспорт",
                    ),
                ),
                page_index=1,
                page_count=2,
                page_start_index=7,
            )

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_review_confirmation_handler,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )
    _patch_next_review_item_after_action(monkeypatch, workspace_id=workspace_id)

    event = callback_event("rcp:categorytoken:1")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Страница 2 из 2" in response.text
    assert response.buttons[0][0].callback_data == "rvc:categorytoken:7"
    assert response.buttons[1][0].callback_data == "rcp:categorytoken:0"


async def test_chat_event_service_returns_to_same_review_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)
    returned_tokens: list[str] = []

    class FakeChatReviewQueueService:
        def __init__(self, _session: object) -> None:
            pass

        async def return_to_review_item(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewReturnSelection,
        ):
            assert context.workspace.id == workspace_id
            returned_tokens.append(selection.action_token)
            return chat_review_dto.StartedChatReviewItem(
                action_token="reviewtoken",
                item=chat_review_dto.ChatReviewQueueItem(
                    document_id=document_id,
                    raw_transaction_id=raw_transaction_id,
                    row_index=0,
                    status="needs_review",
                    account_name="T-Bank Card",
                    operation_date=date(2026, 6, 30),
                    amount=Decimal("-1250.00"),
                    amount_raw=None,
                    currency="RUB",
                    description="MAGNIT",
                    suggested_operation_type="expense",
                    normalization_error=None,
                ),
            )

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_review_queue_handler, "ChatReviewQueueService", FakeChatReviewQueueService
    )

    event = callback_event("rvb:categorytoken")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert returned_tokens == ["categorytoken"]
    assert response is not None
    assert "📝 Описание: MAGNIT" in response.text
    assert response.buttons[0][0].callback_data == "rev:reviewtoken:conf"
    assert response.buttons[2][0].url == (
        f"https://booker.example/app/imports/documents/{document_id}/review#raw-{raw_transaction_id}"
    )


async def test_chat_event_service_confirms_review_item_with_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)
    selected_categories: list[int] = []

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def confirm_with_category(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewCategorySelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "categorytoken"
            selected_categories.append(selection.category_index)
            return chat_review_dto.ChatReviewCategoryActionResult(
                action_result=chat_review_dto.ChatReviewActionResult(
                    action_label="операция подтверждена",
                ),
            )

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_review_confirmation_handler,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )
    _patch_next_review_item_after_action(monkeypatch, workspace_id=workspace_id)

    event = callback_event("rvc:categorytoken:1")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert selected_categories == [1]
    assert response is not None
    assert "NEXT ROW" in response.text
    assert response.callback_notification == "Готово: операция подтверждена"
    assert response.buttons[0][0].callback_data == "rev:nexttoken:conf"


async def test_chat_event_service_shows_property_menu_after_category_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    property_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def confirm_with_category(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewCategorySelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "categorytoken"
            assert selection.category_index == 0
            return chat_review_dto.ChatReviewCategoryActionResult(
                property_selection=chat_review_dto.StartedChatReviewPropertySelection(
                    action_token="propertytoken",
                    item=chat_review_dto.ChatReviewQueueItem(
                        document_id=document_id,
                        raw_transaction_id=raw_transaction_id,
                        row_index=0,
                        status="needs_review",
                        account_name="T-Bank Card",
                        operation_date=date(2026, 6, 30),
                        amount=Decimal("-1250.00"),
                        amount_raw=None,
                        currency="RUB",
                        description="MAGNIT",
                        suggested_operation_type="expense",
                        normalization_error=None,
                    ),
                    category_name="Ремонт",
                    property_choices=(
                        chat_review_dto.ChatReviewPropertyChoice(
                            id=None,
                            name="Без объекта",
                        ),
                        chat_review_dto.ChatReviewPropertyChoice(
                            id=property_id,
                            name="9 Maya",
                        ),
                    ),
                )
            )

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_review_confirmation_handler,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )

    event = callback_event("rvc:categorytoken:0")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Выбери объект" in response.text
    assert "Категория: Ремонт" in response.text
    assert response.buttons[0][0].text == "Без объекта"
    assert response.buttons[0][0].callback_data == "rvp:propertytoken:0"
    assert response.buttons[1][0].text == "9 Maya"
    assert response.buttons[1][0].callback_data == "rvp:propertytoken:1"
    assert response.buttons[2][0].text == "⬅️ Назад"
    assert response.buttons[2][0].callback_data == "rvb:propertytoken"


async def test_chat_event_service_confirms_review_item_with_property(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)
    selected_properties: list[int] = []

    class FakeChatReviewConfirmationService:
        def __init__(self, _session: object, _settings: Settings) -> None:
            pass

        async def confirm_with_property(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewPropertySelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "propertytoken"
            selected_properties.append(selection.property_index)
            return chat_review_dto.ChatReviewCategoryActionResult(
                action_result=chat_review_dto.ChatReviewActionResult(
                    action_label="операция подтверждена",
                ),
            )

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_review_confirmation_handler,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )
    _patch_next_review_item_after_action(monkeypatch, workspace_id=workspace_id)

    event = callback_event("rvp:propertytoken:1")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert selected_properties == [1]
    assert response is not None
    assert "NEXT ROW" in response.text
    assert response.callback_notification == "Готово: операция подтверждена"
    assert response.buttons[0][0].callback_data == "rev:nexttoken:conf"
