from uuid import UUID

from app.db.base import utc_now
from app.features.chat_integrations.actions.review import ChatReviewCallbackData
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.models import ChatConversationState
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.chat_integrations.use_cases.review.dto import ChatReviewCategoryChoice


class ChatReviewStateClaimer:
    @staticmethod
    async def claim_once(
        chat_integrations: ChatIntegrationRepository,
        state: ChatConversationState,
    ) -> None:
        claimed = await chat_integrations.try_consume_active_conversation_state(
            state,
            consumed_at=utc_now(),
        )
        if not claimed:
            raise ChatReviewActionError("Stored review action is invalid.")


class ChatReviewStateReader:
    @staticmethod
    def read_document_id(payload: dict[str, object]) -> UUID:
        return ChatReviewStateReader._read_uuid(payload, "document_id")

    @staticmethod
    def read_raw_transaction_id(payload: dict[str, object]) -> UUID:
        return ChatReviewStateReader._read_uuid(payload, "raw_transaction_id")

    @staticmethod
    def read_category_id(payload: dict[str, object], category_index: int) -> UUID:
        category_ids = payload.get("category_ids")
        if not isinstance(category_ids, list):
            raise ChatReviewActionError("Stored review action does not include categories.")
        if category_index < 0 or category_index >= len(category_ids):
            raise ChatReviewActionError("Selected category is no longer available.")

        category_id = category_ids[category_index]
        if not isinstance(category_id, str):
            raise ChatReviewActionError("Stored category id is invalid.")
        try:
            return UUID(category_id)
        except ValueError as exc:
            raise ChatReviewActionError("Stored category id is invalid.") from exc

    @staticmethod
    def read_category_name(payload: dict[str, object], category_index: int) -> str:
        category_names = payload.get("category_names")
        if not isinstance(category_names, list):
            return "выбранная категория"
        if category_index < 0 or category_index >= len(category_names):
            return "выбранная категория"
        category_name = category_names[category_index]
        return category_name if isinstance(category_name, str) else "выбранная категория"

    @staticmethod
    def read_category_choices(
        payload: dict[str, object],
    ) -> tuple[ChatReviewCategoryChoice, ...]:
        category_ids = payload.get("category_ids")
        category_names = payload.get("category_names")
        if not isinstance(category_ids, list) or not isinstance(category_names, list):
            raise ChatReviewActionError("Stored review action does not include categories.")
        if len(category_ids) != len(category_names):
            raise ChatReviewActionError("Stored review categories are invalid.")

        choices: list[ChatReviewCategoryChoice] = []
        for category_id, category_name in zip(category_ids, category_names, strict=True):
            if not isinstance(category_id, str) or not isinstance(category_name, str):
                raise ChatReviewActionError("Stored review categories are invalid.")
            try:
                parsed_category_id = UUID(category_id)
            except ValueError as exc:
                raise ChatReviewActionError("Stored category id is invalid.") from exc
            choices.append(ChatReviewCategoryChoice(id=parsed_category_id, name=category_name))
        return tuple(choices)

    @staticmethod
    def read_confirm_category_id(payload: dict[str, object]) -> UUID:
        return ChatReviewStateReader._read_uuid(payload, "category_id")

    @staticmethod
    def read_confirm_category_name(payload: dict[str, object]) -> str:
        category_name = payload.get("category_name")
        return category_name if isinstance(category_name, str) else "выбранная категория"

    @staticmethod
    def read_offer_rule_suggestion(payload: dict[str, object]) -> bool:
        return payload.get("offer_rule_suggestion") is True

    @staticmethod
    def read_optional_property_id(payload: dict[str, object]) -> UUID | None:
        property_id = payload.get("property_id")
        if property_id is None:
            return None
        if not isinstance(property_id, str):
            raise ChatReviewActionError("Stored property id is invalid.")
        try:
            return UUID(property_id)
        except ValueError as exc:
            raise ChatReviewActionError("Stored property id is invalid.") from exc

    @staticmethod
    def read_rule_patterns(payload: dict[str, object]) -> tuple[str, ...]:
        patterns = payload.get("patterns")
        if not isinstance(patterns, list):
            raise ChatReviewActionError("Stored rule suggestion is invalid.")
        clean_patterns: list[str] = []
        for pattern in patterns:
            if not isinstance(pattern, str):
                raise ChatReviewActionError("Stored rule suggestion is invalid.")
            clean_patterns.append(pattern)
        if not clean_patterns:
            raise ChatReviewActionError("Stored rule suggestion is invalid.")
        return tuple(clean_patterns)

    @staticmethod
    def read_rule_pattern(payload: dict[str, object], pattern_index: int) -> str:
        patterns = ChatReviewStateReader.read_rule_patterns(payload)
        if pattern_index < 0 or pattern_index >= len(patterns):
            raise ChatReviewActionError("Selected rule pattern is no longer available.")
        return patterns[pattern_index]

    @staticmethod
    def read_review_action(payload: dict[str, object]) -> str:
        review_action = payload.get("review_action")
        if not isinstance(review_action, str):
            raise ChatReviewActionError("Stored review action is invalid.")
        if review_action not in {
            ChatReviewCallbackData.DUPLICATE_ACTION,
            ChatReviewCallbackData.IGNORE_ACTION,
            ChatReviewCallbackData.MARK_UNIQUE_ACTION,
        }:
            raise ChatReviewActionError("Stored review action is invalid.")
        return review_action

    @staticmethod
    def read_property_id(payload: dict[str, object], property_index: int) -> UUID | None:
        property_ids = payload.get("property_ids")
        if not isinstance(property_ids, list):
            raise ChatReviewActionError("Stored review action does not include properties.")
        if property_index < 0 or property_index >= len(property_ids):
            raise ChatReviewActionError("Selected property is no longer available.")

        property_id = property_ids[property_index]
        if property_id is None:
            return None
        if not isinstance(property_id, str):
            raise ChatReviewActionError("Stored property id is invalid.")
        try:
            return UUID(property_id)
        except ValueError as exc:
            raise ChatReviewActionError("Stored property id is invalid.") from exc

    @staticmethod
    def read_transfer_account_id(payload: dict[str, object], account_index: int) -> UUID:
        account_ids = payload.get("account_ids")
        if not isinstance(account_ids, list):
            raise ChatReviewActionError("Stored review action does not include accounts.")
        if account_index < 0 or account_index >= len(account_ids):
            raise ChatReviewActionError("Selected account is no longer available.")

        account_id = account_ids[account_index]
        if not isinstance(account_id, str):
            raise ChatReviewActionError("Stored account id is invalid.")
        try:
            return UUID(account_id)
        except ValueError as exc:
            raise ChatReviewActionError("Stored account id is invalid.") from exc

    @staticmethod
    def read_transfer_account_label(payload: dict[str, object], account_index: int) -> str:
        return ChatReviewStateReader._read_label(
            payload=payload,
            key="account_labels",
            index=account_index,
            fallback="выбранный счет",
        )

    @staticmethod
    def read_matched_raw_transaction_id(payload: dict[str, object], pair_index: int) -> UUID:
        raw_transaction_ids = payload.get("matched_raw_transaction_ids")
        if not isinstance(raw_transaction_ids, list):
            raise ChatReviewActionError("Stored review action does not include matched rows.")
        if pair_index < 0 or pair_index >= len(raw_transaction_ids):
            raise ChatReviewActionError("Selected matched row is no longer available.")

        raw_transaction_id = raw_transaction_ids[pair_index]
        if not isinstance(raw_transaction_id, str):
            raise ChatReviewActionError("Stored matched row id is invalid.")
        try:
            return UUID(raw_transaction_id)
        except ValueError as exc:
            raise ChatReviewActionError("Stored matched row id is invalid.") from exc

    @staticmethod
    def read_matched_raw_transaction_label(payload: dict[str, object], pair_index: int) -> str:
        return ChatReviewStateReader._read_label(
            payload=payload,
            key="matched_raw_transaction_labels",
            index=pair_index,
            fallback="выбранная парная строка",
        )

    @staticmethod
    def read_confirm_transfer_account_id(payload: dict[str, object]) -> UUID | None:
        value = payload.get("counterparty_account_id")
        if value is None:
            return None
        if not isinstance(value, str):
            raise ChatReviewActionError("Stored transfer account is invalid.")
        try:
            return UUID(value)
        except ValueError as exc:
            raise ChatReviewActionError("Stored transfer account is invalid.") from exc

    @staticmethod
    def read_confirm_transfer_matched_raw_transaction_id(
        payload: dict[str, object],
    ) -> UUID | None:
        value = payload.get("matched_raw_transaction_id")
        if value is None:
            return None
        if not isinstance(value, str):
            raise ChatReviewActionError("Stored matched row is invalid.")
        try:
            return UUID(value)
        except ValueError as exc:
            raise ChatReviewActionError("Stored matched row is invalid.") from exc

    @staticmethod
    def read_transfer_action_label(payload: dict[str, object]) -> str:
        action_label = payload.get("action_label")
        if not isinstance(action_label, str):
            return "перевод подтвержден"
        return action_label

    @staticmethod
    def _read_label(
        *,
        payload: dict[str, object],
        key: str,
        index: int,
        fallback: str,
    ) -> str:
        labels = payload.get(key)
        if not isinstance(labels, list):
            return fallback
        if index < 0 or index >= len(labels):
            return fallback
        label = labels[index]
        return label if isinstance(label, str) else fallback

    @staticmethod
    def _read_uuid(payload: dict[str, object], key: str) -> UUID:
        value = payload.get(key)
        if not isinstance(value, str):
            raise ChatReviewActionError("Stored review action is invalid.")
        try:
            return UUID(value)
        except ValueError as exc:
            raise ChatReviewActionError("Stored review action is invalid.") from exc
