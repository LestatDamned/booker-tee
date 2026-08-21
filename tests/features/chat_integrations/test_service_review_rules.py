from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.chat_integrations.actions.review import (
    ChatReviewCategorySelection,
    ChatReviewRuleSuggestionSelection,
)
from app.features.chat_integrations.handlers import manual as chat_manual_handler
from app.features.chat_integrations.handlers import (
    review_confirmation as chat_review_confirmation_handler,
)
from app.features.chat_integrations.handlers import review_queue as chat_review_queue_handler
from app.features.chat_integrations.handlers import (
    review_rule_suggestion as chat_review_rule_suggestion_handler,
)
from app.features.chat_integrations.service import ChatEventService
from app.features.chat_integrations.use_cases.review import (
    dto as chat_review_dto,
)
from app.features.chat_integrations.use_cases.review.rules import (
    ChatReviewRuleSuggestionService,
)
from app.features.workspaces.service import WorkspaceContext

from .chat_test_support import (
    bound_chat_workspace,
    callback_event,
    message_event,
    patch_bound_workspace,
)


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


async def test_chat_rule_claims_action_and_uses_shared_creator_before_commit() -> None:
    events: list[str] = []
    calls: list[dict[str, object]] = []
    workspace_id = uuid4()
    document_id = uuid4()
    raw_transaction_id = uuid4()
    category_id = uuid4()
    state = SimpleNamespace(
        step="suggest_rule",
        state_payload={
            "document_id": str(document_id),
            "raw_transaction_id": str(raw_transaction_id),
            "category_id": str(category_id),
            "property_id": None,
            "patterns": ["ПЯТЁРОЧКА"],
        },
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
            return SimpleNamespace(row_index=3)

    class RuleCreatorStub:
        async def create_and_apply(self, **kwargs: object) -> None:
            events.append("create_rule")
            calls.append(kwargs)

    session = SessionStub()
    service = ChatReviewRuleSuggestionService(cast(AsyncSession, session))
    service.chat_integrations = cast(Any, ChatIntegrationsStub())
    service.review_queue = cast(Any, ReviewQueueStub())
    service.review_rules = cast(Any, RuleCreatorStub())
    context = WorkspaceContext(
        user=cast(Any, SimpleNamespace(id=uuid4())),
        workspace=cast(Any, SimpleNamespace(id=workspace_id)),
        membership=cast(Any, SimpleNamespace(id=uuid4())),
    )

    result = await service.save_suggestion(
        context=context,
        selection=ChatReviewRuleSuggestionSelection(
            action_token="ruletoken",
            action="save",
        ),
    )

    assert events == ["claim", "create_rule", "commit"]
    assert calls == [
        {
            "context": context,
            "document_id": document_id,
            "item_id": raw_transaction_id,
            "category_id": category_id,
            "property_id": None,
            "pattern": "ПЯТЁРОЧКА",
        }
    ]
    assert result.continuation_anchor == chat_review_dto.ChatReviewContinuationAnchor(
        document_id=document_id,
        row_index=3,
    )


async def test_chat_event_service_shows_rule_suggestion_after_manual_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
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
            return chat_review_dto.ChatReviewCategoryActionResult(
                action_result=chat_review_dto.ChatReviewActionResult(
                    action_label="операция подтверждена",
                ),
                rule_suggestion=chat_review_dto.StartedChatReviewRuleSuggestion(
                    action_token="ruletoken",
                    action_label="операция подтверждена",
                    pattern="KRASNOE&BELOE",
                    alternative_patterns=("KRASNOE",),
                    category_name="Продукты",
                ),
            )

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_review_confirmation_handler,
        "ChatReviewConfirmationService",
        FakeChatReviewConfirmationService,
    )

    event = callback_event("rvc:categorytoken:1")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Запомнить для похожих операций?" in response.text
    assert "Признак: KRASNOE&BELOE" in response.text
    assert response.buttons[0][0].callback_data == "rvr:ruletoken:save"
    assert response.buttons[1][0].callback_data == "rvr:ruletoken:pick"


async def test_chat_event_service_saves_review_rule_suggestion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)
    saved_tokens: list[str] = []

    class FakeChatReviewRuleSuggestionService:
        def __init__(self, _session: object) -> None:
            pass

        async def save_suggestion(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewRuleSuggestionSelection,
        ):
            assert context.workspace.id == workspace_id
            saved_tokens.append(selection.action_token)
            return chat_review_dto.ChatReviewRuleActionResult(
                action_label="правило сохранено",
            )

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_review_rule_suggestion_handler,
        "ChatReviewRuleSuggestionService",
        FakeChatReviewRuleSuggestionService,
    )
    _patch_next_review_item_after_action(monkeypatch, workspace_id=workspace_id)

    event = callback_event("rvr:ruletoken:save")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert saved_tokens == ["ruletoken"]
    assert response is not None
    assert response.callback_notification == "Готово: правило сохранено"
    assert "NEXT ROW" in response.text


async def test_chat_event_service_starts_manual_rule_pattern_input(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)

    class FakeChatReviewRuleSuggestionService:
        def __init__(self, _session: object) -> None:
            pass

        async def start_manual_pattern_input(
            self,
            *,
            context: WorkspaceContext,
            selection: ChatReviewRuleSuggestionSelection,
        ):
            assert context.workspace.id == workspace_id
            assert selection.action_token == "ruletoken"
            return chat_review_dto.StartedChatReviewRulePatternInput(
                action_token="manualruletoken",
                category_name="Продукты",
            )

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_review_rule_suggestion_handler,
        "ChatReviewRuleSuggestionService",
        FakeChatReviewRuleSuggestionService,
    )

    event = callback_event("rvr:ruletoken:type")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert response is not None
    assert "Напиши признак" in response.text
    assert response.buttons[0][0].callback_data == "rvr:manualruletoken:skip"


async def test_chat_event_service_saves_manual_rule_pattern_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    bound_workspace = bound_chat_workspace(workspace_id)
    saved_texts: list[str | None] = []

    class FakeChatReviewRuleSuggestionService:
        def __init__(self, _session: object) -> None:
            pass

        async def save_manual_pattern(
            self,
            *,
            context: WorkspaceContext,
            text: str | None,
        ):
            assert context.workspace.id == workspace_id
            saved_texts.append(text)
            return chat_review_dto.ChatReviewRuleActionResult(
                action_label="правило сохранено",
            )

    class FakeChatManualOperationService:
        def __init__(self, _session: object) -> None:
            pass

        async def continue_from_text_input(
            self,
            *,
            context: WorkspaceContext,
            text: str | None,
        ):
            assert context.workspace.id == workspace_id
            assert text == "KRASNOE&BELOE"
            return None

    patch_bound_workspace(monkeypatch, bound_workspace)
    monkeypatch.setattr(
        chat_manual_handler,
        "ChatManualOperationService",
        FakeChatManualOperationService,
    )
    monkeypatch.setattr(
        chat_review_rule_suggestion_handler,
        "ChatReviewRuleSuggestionService",
        FakeChatReviewRuleSuggestionService,
    )
    _patch_next_review_item_after_action(monkeypatch, workspace_id=workspace_id)

    event = message_event("KRASNOE&BELOE")

    response = await ChatEventService(
        cast(AsyncSession, object()),
        Settings(public_base_url="https://booker.example"),
    ).receive_inbound_event(event)

    assert saved_texts == ["KRASNOE&BELOE"]
    assert response is not None
    assert response.callback_notification == "Готово: правило сохранено"
    assert "NEXT ROW" in response.text
