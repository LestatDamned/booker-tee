import re
from decimal import Decimal
from uuid import UUID

from app.features.accounts.models import Account
from app.features.categories.models import Category, CategoryKind
from app.features.chat_integrations.errors import ChatReviewActionError
from app.features.chat_integrations.use_cases.review.config import (
    CHAT_REVIEW_CATEGORY_PAGE_SIZE,
    CHAT_REVIEW_PROPERTY_MAX_CHOICES,
    CHAT_REVIEW_TRANSFER_ACCOUNT_MAX_CHOICES,
    CHAT_REVIEW_TRANSFER_PAIR_MAX_CHOICES,
)
from app.features.chat_integrations.use_cases.review.dto import (
    ChatReviewCategoryChoice,
    ChatReviewExistingTransferChoice,
    ChatReviewPropertyChoice,
    ChatReviewQueueItem,
    ChatReviewTransferAccountChoice,
    ChatReviewTransferPairChoice,
    StartedChatReviewCategorySelection,
)
from app.features.chat_integrations.use_cases.review.state import ChatReviewStateReader
from app.features.import_review.application.commands.transfers import (
    CreateImportReviewTransferCommand,
    ImportReviewTransferCommand,
    LinkImportReviewExistingTransferCommand,
    MatchImportReviewRawRowCommand,
)
from app.features.import_review.application.queries.transfer_suggestions import (
    ExistingTransferSuggestion,
    TransferSuggestion,
)
from app.features.imports.models import RawTransaction
from app.features.properties.models import Property
from app.features.transaction_rules.domain.patterns import infer_rule_pattern
from app.features.transaction_rules.domain.text import clean_rule_pattern, normalized_text
from app.features.transaction_rules.errors import TransactionRuleError


class ChatReviewCategoryChoiceBuilder:
    @staticmethod
    def build_choices(
        *,
        item: ChatReviewQueueItem,
        categories: list[Category],
    ) -> tuple[ChatReviewCategoryChoice, ...]:
        accepted_kinds = ChatReviewCategoryChoiceBuilder._accepted_kinds(item)
        excluded_system_keys = {"transfer", "adjustment", "duplicate", "ignore"}
        choices: list[Category] = []
        chosen_ids: set[UUID] = set()

        suggested = next(
            (category for category in categories if category.id == item.suggested_category_id),
            None,
        )
        if suggested is not None and ChatReviewCategoryChoiceBuilder._is_available_category(
            suggested,
            accepted_kinds,
            excluded_system_keys,
        ):
            choices.append(suggested)
            chosen_ids.add(suggested.id)

        for category in categories:
            if category.id in chosen_ids:
                continue
            if not ChatReviewCategoryChoiceBuilder._is_available_category(
                category,
                accepted_kinds,
                excluded_system_keys,
            ):
                continue
            choices.append(category)
            chosen_ids.add(category.id)

        return tuple(
            ChatReviewCategoryChoice(id=category.id, name=category.name) for category in choices
        )

    @staticmethod
    def _accepted_kinds(item: ChatReviewQueueItem) -> set[CategoryKind]:
        if item.suggested_operation_type == "income" or (
            item.suggested_operation_type is None
            and item.amount is not None
            and item.amount > Decimal("0")
        ):
            return {CategoryKind.INCOME, CategoryKind.MIXED}
        if item.suggested_operation_type == "expense" or (
            item.suggested_operation_type is None
            and item.amount is not None
            and item.amount < Decimal("0")
        ):
            return {CategoryKind.EXPENSE, CategoryKind.MIXED}
        return {CategoryKind.INCOME, CategoryKind.EXPENSE, CategoryKind.MIXED}

    @staticmethod
    def _is_available_category(
        category: Category,
        accepted_kinds: set[CategoryKind],
        excluded_system_keys: set[str],
    ) -> bool:
        return (
            category.is_active
            and category.kind in accepted_kinds
            and category.system_key not in excluded_system_keys
        )


class ChatReviewCategoryPageBuilder:
    @staticmethod
    def build_selection(
        *,
        action_token: str,
        item: ChatReviewQueueItem,
        category_choices: tuple[ChatReviewCategoryChoice, ...],
        page_index: int,
    ) -> StartedChatReviewCategorySelection:
        page_count = max(
            1,
            (len(category_choices) + CHAT_REVIEW_CATEGORY_PAGE_SIZE - 1)
            // CHAT_REVIEW_CATEGORY_PAGE_SIZE,
        )
        normalized_page_index = min(max(page_index, 0), page_count - 1)
        page_start_index = normalized_page_index * CHAT_REVIEW_CATEGORY_PAGE_SIZE
        page_end_index = page_start_index + CHAT_REVIEW_CATEGORY_PAGE_SIZE
        return StartedChatReviewCategorySelection(
            action_token=action_token,
            item=item,
            category_choices=category_choices[page_start_index:page_end_index],
            page_index=normalized_page_index,
            page_count=page_count,
            page_start_index=page_start_index,
        )


class ChatReviewPropertyChoiceBuilder:
    @staticmethod
    def build_choices(properties: list[Property]) -> tuple[ChatReviewPropertyChoice, ...]:
        choices = [ChatReviewPropertyChoice(id=None, name="Без объекта")]
        choices.extend(
            ChatReviewPropertyChoice(
                id=property_.id,
                name=property_.short_name or property_.name,
            )
            for property_ in properties[:CHAT_REVIEW_PROPERTY_MAX_CHOICES]
        )
        return tuple(choices)


class ChatReviewRulePatternBuilder:
    GENERIC_TOKENS = {
        "ao",
        "банк",
        "карта",
        "карте",
        "операция",
        "оплата",
        "перевод",
        "платеж",
        "покупка",
        "средств",
        "списание",
        "транзакции",
        "экспобанк",
    }

    @classmethod
    def build_choices(cls, raw_transaction: RawTransaction) -> tuple[str, ...]:
        try:
            inferred_pattern = infer_rule_pattern(raw_transaction)
        except TransactionRuleError:
            return ()

        choices: list[str] = []
        for candidate in (inferred_pattern, *cls._split_pattern(inferred_pattern)):
            cleaned = cls._clean_candidate(candidate)
            if cleaned is None or cleaned in choices:
                continue
            choices.append(cleaned)
        return tuple(choices[:4])

    @classmethod
    def clean_manual_pattern(cls, value: str | None) -> str:
        cleaned = cls._clean_candidate(value or "")
        if cleaned is None:
            raise ChatReviewActionError(
                "Напиши более точный признак: минимум 3 буквы или цифры, без номера карты."
            )
        return cleaned

    @classmethod
    def _split_pattern(cls, pattern: str) -> tuple[str, ...]:
        candidates = re.split(r"[&*/|,;]+|\s+", pattern)
        return tuple(candidate for candidate in candidates if candidate)

    @classmethod
    def _clean_candidate(cls, candidate: str) -> str | None:
        try:
            cleaned = clean_rule_pattern(candidate)
        except TransactionRuleError:
            return None
        if len(cleaned) < 3 or len(cleaned) > 80:
            return None
        normalized = normalized_text(cleaned)
        if len(normalized) < 3:
            return None
        tokens = set(normalized.split())
        if not tokens or tokens.issubset(cls.GENERIC_TOKENS):
            return None
        if "xxxx" in cleaned.casefold():
            return None
        return cleaned


class ChatReviewTransferAccountChoiceBuilder:
    @staticmethod
    def build_choices(
        *,
        item: ChatReviewQueueItem,
        accounts: list[Account],
    ) -> tuple[ChatReviewTransferAccountChoice, ...]:
        choices: list[ChatReviewTransferAccountChoice] = []
        for account in accounts:
            if account.id == item.source_account_id:
                continue
            if item.currency is not None and account.currency != item.currency:
                continue
            choices.append(
                ChatReviewTransferAccountChoice(
                    id=account.id,
                    name=account.name,
                    currency=account.currency,
                )
            )
            if len(choices) >= CHAT_REVIEW_TRANSFER_ACCOUNT_MAX_CHOICES:
                break
        return tuple(choices)


class ChatReviewTransferPairChoiceBuilder:
    @staticmethod
    def build_choices(
        suggestions: list[TransferSuggestion],
    ) -> tuple[ChatReviewTransferPairChoice, ...]:
        choices: list[ChatReviewTransferPairChoice] = []
        for suggestion in suggestions[:CHAT_REVIEW_TRANSFER_PAIR_MAX_CHOICES]:
            raw_transaction = suggestion.raw_transaction
            choices.append(
                ChatReviewTransferPairChoice(
                    id=raw_transaction.id,
                    account_name=raw_transaction.account.name
                    if raw_transaction.account is not None
                    else None,
                    operation_date=raw_transaction.operation_date,
                    amount=raw_transaction.amount,
                    currency=raw_transaction.currency,
                    description=(
                        raw_transaction.description_normalized or raw_transaction.description_raw
                    ),
                    day_distance=suggestion.day_distance,
                )
            )
        return tuple(choices)


class ChatReviewExistingTransferChoiceBuilder:
    @staticmethod
    def build_choices(
        suggestions: list[ExistingTransferSuggestion],
    ) -> tuple[ChatReviewExistingTransferChoice, ...]:
        choices: list[ChatReviewExistingTransferChoice] = []
        for suggestion in suggestions[:CHAT_REVIEW_TRANSFER_PAIR_MAX_CHOICES]:
            counterparty = suggestion.counterparty_entry
            if counterparty is None:
                continue
            choices.append(
                ChatReviewExistingTransferChoice(
                    id=suggestion.operation.id,
                    operation_date=suggestion.operation.operation_date,
                    account_name=suggestion.account_entry.account.name,
                    account_amount=suggestion.account_entry.amount,
                    account_currency=suggestion.account_entry.currency,
                    counterparty_account_name=counterparty.account.name,
                    counterparty_amount=counterparty.amount,
                    counterparty_currency=counterparty.currency,
                    description=suggestion.operation.description,
                    day_distance=suggestion.day_distance,
                )
            )
        return tuple(choices)


class ChatReviewTransferLabelBuilder:
    @staticmethod
    def account_label(choice: ChatReviewTransferAccountChoice) -> str:
        return f"{choice.name} / {choice.currency}"

    @staticmethod
    def pair_label(choice: ChatReviewTransferPairChoice) -> str:
        date_label = (
            choice.operation_date.strftime("%d.%m.%Y")
            if choice.operation_date is not None
            else "дата?"
        )
        amount_label = "сумма?"
        if choice.amount is not None:
            amount_label = f"{choice.amount:.2f} {choice.currency or ''}".strip()
        account_label = choice.account_name or "счет?"
        return f"Пара: {account_label} / {date_label} / {amount_label}"

    @staticmethod
    def existing_label(choice: ChatReviewExistingTransferChoice) -> str:
        date_label = choice.operation_date.strftime("%d.%m.%Y")
        counterparty_label = choice.counterparty_account_name or "второй счет?"
        amount_label = "сумма?"
        if choice.counterparty_amount is not None:
            amount_label = (
                f"{choice.counterparty_amount:.2f} {choice.counterparty_currency or ''}".strip()
            )
        return f"Созданный: {counterparty_label} / {date_label} / {amount_label}"


class ChatReviewTransferCommandBuilder:
    @staticmethod
    def build_command(
        payload: dict[str, object],
        *,
        idempotency_key: UUID,
    ) -> ImportReviewTransferCommand:
        document_id = ChatReviewStateReader.read_document_id(payload)
        raw_transaction_id = ChatReviewStateReader.read_raw_transaction_id(payload)
        counterparty_account_id = ChatReviewStateReader.read_confirm_transfer_account_id(payload)
        if counterparty_account_id is not None:
            return CreateImportReviewTransferCommand(
                document_id=document_id,
                item_id=raw_transaction_id,
                counterparty_account_id=counterparty_account_id,
                idempotency_key=idempotency_key,
            )

        matched_raw_transaction_id = (
            ChatReviewStateReader.read_confirm_transfer_matched_raw_transaction_id(payload)
        )
        if matched_raw_transaction_id is not None:
            return MatchImportReviewRawRowCommand(
                document_id=document_id,
                item_id=raw_transaction_id,
                matched_item_id=matched_raw_transaction_id,
                idempotency_key=idempotency_key,
            )

        matched_operation_id = ChatReviewStateReader.read_confirm_transfer_matched_operation_id(
            payload
        )
        if matched_operation_id is not None:
            return LinkImportReviewExistingTransferCommand(
                document_id=document_id,
                item_id=raw_transaction_id,
                operation_id=matched_operation_id,
                idempotency_key=idempotency_key,
            )

        raise ChatReviewActionError("Stored transfer action is invalid.")
