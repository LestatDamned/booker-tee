from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from app.features.imports.models import RawTransactionStatus
from app.features.imports.presentation.review.models import ClassificationVM
from app.features.imports.presentation.review.references import ReviewReferenceResolver
from app.features.ledger.models import OperationType

FINAL_RAW_STATUSES = {
    RawTransactionStatus.CONFIRMED,
    RawTransactionStatus.MATCHED,
    RawTransactionStatus.IGNORED,
    RawTransactionStatus.DUPLICATE,
}


class ReviewRuleSuggestionResolver:
    @staticmethod
    def has_active_suggestion(row: object) -> bool:
        status = ReviewReferenceResolver.enum_or_none(
            RawTransactionStatus,
            getattr(row, "status", None),
        )
        return (
            status == RawTransactionStatus.SUGGESTED
            or getattr(row, "suggested_by_rule_id", None) is not None
        )

    @staticmethod
    def rule_suggestion(row: object) -> dict[str, object] | None:
        raw_payload = getattr(row, "raw_payload", None)
        if not isinstance(raw_payload, dict):
            return None
        suggestion = raw_payload.get("rule_suggestion")
        return suggestion if isinstance(suggestion, dict) else None

    @staticmethod
    def rule_auto_applied(row: object) -> bool:
        suggestion = ReviewRuleSuggestionResolver.rule_suggestion(row)
        return bool(suggestion and suggestion.get("application_mode") == "auto_apply")


class ReviewClassificationResolver:
    def resolve(self, row: object) -> ClassificationVM:
        explicit = ReviewReferenceResolver.enum_or_none(
            OperationType,
            getattr(row, "operation_type", None),
        )
        if explicit is not None:
            return ClassificationVM(explicit, "explicit")

        suggested = ReviewReferenceResolver.enum_or_none(
            OperationType,
            getattr(row, "suggested_operation_type", None),
        )
        if suggested is not None:
            return ClassificationVM(suggested, "suggested")

        amount = getattr(row, "amount", None)
        if isinstance(amount, Decimal):
            if amount > 0:
                return ClassificationVM(OperationType.INCOME, "inferred")
            if amount < 0:
                return ClassificationVM(OperationType.EXPENSE, "inferred")

        return ClassificationVM(None, "unknown")


class ReviewConfirmabilityPolicy:
    def __init__(self, *, categories: Sequence[object]) -> None:
        self.categories = categories

    def check(
        self,
        row: object,
        *,
        document: object,
        classification: ClassificationVM,
        selected_category_id: UUID | None,
    ) -> list[str]:
        status = ReviewReferenceResolver.enum_or_none(
            RawTransactionStatus,
            getattr(row, "status", None),
        )
        if status in FINAL_RAW_STATUSES or status == RawTransactionStatus.FAILED:
            return ["строка уже в финальном состоянии"]
        if getattr(row, "normalization_error", None):
            return ["есть ошибка нормализации"]

        problems: list[str] = []
        if not (getattr(row, "operation_date", None) or getattr(row, "operation_date_raw", None)):
            problems.append("нет даты операции")
        if getattr(row, "amount", None) is None:
            problems.append("нет суммы")
        if not getattr(row, "currency", None):
            problems.append("нет валюты")
        if ReviewReferenceResolver.source_account_id(row, document) is None:
            problems.append("нет исходного счета")
        if classification.operation_type is None:
            problems.append("не выбран тип операции")
            return problems

        if classification.operation_type in {OperationType.INCOME, OperationType.EXPENSE}:
            category = ReviewReferenceResolver.category_by_id(
                self.categories,
                selected_category_id,
            )
            if (
                selected_category_id is None
                or getattr(category, "system_key", None) == "uncategorized"
            ):
                problems.append("для дохода или расхода нужна категория")
        elif classification.operation_type == OperationType.TRANSFER:
            source_id = ReviewReferenceResolver.source_account_id(row, document)
            counterparty_id = ReviewReferenceResolver.counterparty_account_id(row)
            if source_id is None or counterparty_id is None:
                problems.append("для перевода нужны два счета")
            elif source_id == counterparty_id:
                problems.append("счета перевода должны отличаться")
        else:
            problems.append("этот тип операции нельзя подтвердить из импорта")
        return problems


class ReviewStateResolver:
    def resolve(self, row: object, *, is_confirmable: bool) -> str:
        status = ReviewReferenceResolver.enum_or_none(
            RawTransactionStatus,
            getattr(row, "status", None),
        )
        if status in FINAL_RAW_STATUSES:
            return status.value
        if status == RawTransactionStatus.FAILED or getattr(row, "normalization_error", None):
            return RawTransactionStatus.FAILED.value
        if status == RawTransactionStatus.POSSIBLE_DUPLICATE:
            return RawTransactionStatus.POSSIBLE_DUPLICATE.value
        if ReviewRuleSuggestionResolver.has_active_suggestion(row):
            return RawTransactionStatus.SUGGESTED.value
        if is_confirmable:
            return "ready_to_confirm"
        return RawTransactionStatus.NEEDS_REVIEW.value


class ReviewQueueResolver:
    def first_remaining_raw_transaction_id(self, document: object) -> UUID | None:
        for row in getattr(document, "raw_transactions", []):
            status = ReviewReferenceResolver.enum_or_none(
                RawTransactionStatus,
                getattr(row, "status", None),
            )
            if status not in FINAL_RAW_STATUSES:
                return getattr(row, "id", None)
        return None
