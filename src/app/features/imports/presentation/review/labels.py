from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from app.features.imports.presentation.review.models import ClassificationVM, OperationLinkVM
from app.features.imports.presentation.review.references import ReviewReferenceResolver
from app.features.imports.presentation.review.state import ReviewRuleSuggestionResolver
from app.features.ledger.models import OperationType


class ReviewLabeler:
    def raw_status(self, value: object) -> str:
        labels = {
            "confirmed": "подтверждено",
            "matched": "сопоставлено",
            "ignored": "игнор",
            "duplicate": "дубль",
            "failed": "ошибка",
            "possible_duplicate": "возможный дубль",
            "suggested": "предложено",
            "ready_to_confirm": "готово",
            "needs_review": "нужна проверка",
            "normalized": "нормализовано",
        }
        raw_value = getattr(value, "value", value)
        return labels.get(str(raw_value), str(raw_value or ""))

    def operation_type(self, operation_type: OperationType | None) -> str:
        labels = {
            OperationType.INCOME: "доход",
            OperationType.EXPENSE: "расход",
            OperationType.TRANSFER: "перевод",
            OperationType.ADJUSTMENT: "корректировка",
        }
        return labels.get(operation_type, "тип не выбран")

    def operation_type_value(self, operation_type: OperationType | None) -> str:
        return operation_type.value if operation_type is not None else "muted"

    def operation_type_source(self, source: str) -> str:
        return {
            "explicit": "выбрано",
            "suggested": "предложено",
            "inferred": "по сумме",
            "unknown": "не ясно",
        }.get(source, source)

    def description(self, row: object) -> str:
        return str(
            getattr(row, "description_normalized", None)
            or getattr(row, "description_raw", None)
            or ""
        )

    def classification_label(self, classification: ClassificationVM) -> str:
        return self.operation_type(classification.operation_type)

    def classification_tone(self, classification: ClassificationVM) -> str:
        return self.operation_type_value(classification.operation_type)

    def classification_source_label(self, classification: ClassificationVM) -> str:
        return self.operation_type_source(classification.source)


class ReviewDateLabeler:
    def date(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y")
        if isinstance(value, date):
            return value.strftime("%d.%m.%Y")
        raw_value = str(value)
        try:
            return date.fromisoformat(raw_value).strftime("%d.%m.%Y")
        except ValueError:
            return raw_value


class ReviewMoneyTonePresenter:
    def tone(self, amount: object, operation_type: OperationType | None) -> str:
        if operation_type == OperationType.TRANSFER:
            return "money-transfer"
        if isinstance(amount, Decimal):
            if amount > 0:
                return "money-income"
            if amount < 0:
                return "money-expense"
        return ""


class ReviewAccountLabeler:
    def account(self, row: object, document: object, accounts: Sequence[object]) -> str:
        account_id = ReviewReferenceResolver.source_account_id(row, document)
        account = ReviewReferenceResolver.object_by_id(accounts, account_id)
        if account is not None:
            return str(getattr(account, "name", ""))
        account = getattr(row, "account", None) or getattr(document, "account", None)
        if account is not None:
            return str(getattr(account, "name", ""))
        return "счет не найден" if account_id else "счет не выбран"


class ReviewProposalSummaryPresenter:
    def summary(
        self,
        row: object,
        *,
        category: object | None,
        property_: object | None,
    ) -> str | None:
        if (
            not ReviewRuleSuggestionResolver.has_active_suggestion(row)
            and category is None
            and property_ is None
        ):
            return None
        parts = []
        suggestion = ReviewRuleSuggestionResolver.rule_suggestion(row)
        if suggestion:
            label = (
                "автоправило" if ReviewRuleSuggestionResolver.rule_auto_applied(row) else "правило"
            )
            pattern = suggestion.get("pattern")
            parts.append(f"{label}: {pattern}" if pattern else label)
        parts.append(f"категория: {getattr(category, 'name', 'без категории')}")
        property_name = getattr(property_, "name", None)
        if property_name:
            parts.append(f"объект: {property_name}")
        return " · ".join(parts)


class ReviewOperationLinkPresenter:
    def __init__(self, *, labeler: ReviewLabeler | None = None) -> None:
        self.labeler = labeler or ReviewLabeler()

    def operation_link(self, operation: object | None) -> OperationLinkVM | None:
        if operation is None:
            return None
        operation_id = getattr(operation, "id", None)
        if operation_id is None:
            return None
        operation_type = ReviewReferenceResolver.enum_or_none(
            OperationType,
            getattr(operation, "type", None),
        )
        route = self.operation_route(operation)
        return OperationLinkVM(
            title="Проведено",
            detail=route or self.labeler.description(operation),
            operation_id=operation_id,
            type_value=operation_type.value if isinstance(operation_type, OperationType) else None,
            type_label=self.labeler.operation_type(operation_type)
            if isinstance(operation_type, OperationType)
            else None,
        )

    def operation_route(self, operation: object) -> str:
        money_entries = getattr(operation, "money_entries", []) or []
        from_entry = next((entry for entry in money_entries if self.entry_amount(entry) < 0), None)
        to_entry = next((entry for entry in money_entries if self.entry_amount(entry) > 0), None)
        operation_type = ReviewReferenceResolver.enum_or_none(
            OperationType,
            getattr(operation, "type", None),
        )
        if operation_type == OperationType.TRANSFER:
            return (
                f"перевод: {self.entry_account_name(from_entry)}"
                f" -> {self.entry_account_name(to_entry)}"
            )
        parts = self.operation_meaning(operation)
        if parts:
            return " · ".join(parts)
        parts = []
        if to_entry is not None:
            parts.append(f"на счет: {self.entry_account_name(to_entry)}")
        if from_entry is not None:
            parts.append(f"со счета: {self.entry_account_name(from_entry)}")
        return " · ".join(parts)

    def operation_meaning(self, operation: object) -> list[str]:
        parts: list[str] = []
        category = getattr(operation, "category", None)
        category_name = getattr(category, "name", None)
        if category_name:
            parts.append(str(category_name))
        property_ = getattr(operation, "property", None)
        property_name = getattr(property_, "name", None)
        if property_name:
            parts.append(f"объект: {property_name}")
        return parts

    def entry_account_name(self, entry: object | None) -> str:
        account = getattr(entry, "account", None) if entry is not None else None
        return str(getattr(account, "name", "счет не найден"))

    def entry_amount(self, entry: object) -> Decimal:
        amount = getattr(entry, "amount", None)
        return amount if isinstance(amount, Decimal) else Decimal("0")
