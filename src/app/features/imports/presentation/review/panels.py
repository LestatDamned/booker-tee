from collections.abc import Mapping, Sequence
from decimal import Decimal
from uuid import UUID

from app.features.categories.models import CategoryKind
from app.features.imports.presentation.review.labels import ReviewDateLabeler
from app.features.imports.presentation.review.models import (
    CategoryKindOptionVM,
    CategoryOptionVM,
    CategoryPanelPayload,
    PropertyOptionVM,
    TransferAccountOptionVM,
    TransferMatchOptionVM,
    TransferPanelPayload,
)
from app.features.imports.presentation.review.references import ReviewReferenceResolver


class ReviewPanelPresenter:
    def __init__(
        self,
        *,
        document: object,
        accounts: Sequence[object],
        categories: Sequence[object],
        properties: Sequence[object],
        transfer_suggestions: Mapping[UUID, Sequence[object]],
        existing_transfer_suggestions: Mapping[UUID, Sequence[object]],
        selected_category_id_by_row: Mapping[UUID, UUID] | None = None,
        open_category_editor_by_row: Mapping[UUID, bool] | None = None,
        category_dialog_error_by_row: Mapping[UUID, str] | None = None,
        category_dialog_name_by_row: Mapping[UUID, str] | None = None,
    ) -> None:
        self.document = document
        self.accounts = accounts
        self.categories = categories
        self.properties = properties
        self.transfer_suggestions = transfer_suggestions
        self.existing_transfer_suggestions = existing_transfer_suggestions
        self.selected_category_id_by_row = selected_category_id_by_row or {}
        self.open_category_editor_by_row = open_category_editor_by_row or {}
        self.category_dialog_error_by_row = category_dialog_error_by_row or {}
        self.category_dialog_name_by_row = category_dialog_name_by_row or {}
        self.date_labeler = ReviewDateLabeler()

    def category_panel(self, row: object) -> CategoryPanelPayload:
        row_id = ReviewReferenceResolver.required_id(row)
        selected_category_id = self.selected_category_id_by_row.get(
            row_id,
            getattr(row, "suggested_category_id", None),
        )
        selected_property_id = getattr(row, "suggested_property_id", None)
        return CategoryPanelPayload(
            action_url=(
                f"/imports/documents/{ReviewReferenceResolver.required_id(self.document)}"
                f"/raw-transactions/{row_id}/status"
            ),
            create_category_url=(
                f"/imports/documents/{ReviewReferenceResolver.required_id(self.document)}"
                f"/raw-transactions/{row_id}/categories"
            ),
            selected_category_id=selected_category_id,
            category_options=[
                CategoryOptionVM(
                    id=ReviewReferenceResolver.required_id(category),
                    label=getattr(category, "name", ""),
                    selected=getattr(category, "id", None) == selected_category_id,
                )
                for category in self.categories
            ],
            category_kind_options=self.category_kind_options(row),
            property_options=[
                PropertyOptionVM(
                    id=ReviewReferenceResolver.required_id(property_),
                    label=getattr(property_, "name", ""),
                    selected=getattr(property_, "id", None) == selected_property_id,
                )
                for property_ in self.properties
            ],
            selected_property_id=selected_property_id,
            open_category_editor=self.open_category_editor_by_row.get(row_id, False),
            category_dialog_error=self.category_dialog_error_by_row.get(row_id),
            category_dialog_name=self.category_dialog_name_by_row.get(row_id, ""),
        )

    def category_kind_options(self, row: object) -> list[CategoryKindOptionVM]:
        selected_kind = self.default_category_kind(row)
        labels = {
            CategoryKind.INCOME: "доход",
            CategoryKind.EXPENSE: "расход",
            CategoryKind.TRANSFER: "перевод",
            CategoryKind.ADJUSTMENT: "корректировка",
            CategoryKind.MIXED: "смешанная",
        }
        return [
            CategoryKindOptionVM(
                value=kind.value,
                label=labels[kind],
                selected=kind == selected_kind,
            )
            for kind in CategoryKind
        ]

    def default_category_kind(self, row: object) -> CategoryKind:
        amount = getattr(row, "amount", None)
        if isinstance(amount, Decimal):
            if amount > 0:
                return CategoryKind.INCOME
            if amount < 0:
                return CategoryKind.EXPENSE
        return CategoryKind.MIXED

    def transfer_panel(self, row: object) -> TransferPanelPayload:
        row_id = ReviewReferenceResolver.required_id(row)
        source_account_id = ReviewReferenceResolver.source_account_id(row, self.document)
        match_options = [
            *self.raw_transfer_match_options(row_id),
            *self.existing_transfer_match_options(row_id),
        ]
        return TransferPanelPayload(
            action_url=(
                f"/imports/documents/{ReviewReferenceResolver.required_id(self.document)}"
                f"/raw-transactions/{row_id}/status"
            ),
            account_options=[
                TransferAccountOptionVM(
                    id=ReviewReferenceResolver.required_id(account),
                    label=getattr(account, "name", ""),
                )
                for account in self.accounts
                if getattr(account, "id", None) != source_account_id
            ],
            match_options=[
                TransferMatchOptionVM(
                    value="new",
                    label="создать новый перевод на выбранный счет",
                    account_id=None,
                ),
                *match_options,
            ],
            empty_match_message=self.empty_transfer_match_message(match_options),
            manual_operation_note=self.manual_operation_note(match_options),
        )

    def empty_transfer_match_message(
        self,
        match_options: Sequence[TransferMatchOptionVM],
    ) -> str | None:
        if match_options:
            return None
        return "Подходящих строк выписки или ручных переводов не найдено."

    def manual_operation_note(
        self,
        match_options: Sequence[TransferMatchOptionVM],
    ) -> str | None:
        if match_options:
            return None
        return (
            "Нет подходящих строк выписки или ручных переводов. "
            "Ручной доход или расход сначала нужно исправить на перевод."
        )

    def raw_transfer_match_options(self, row_id: UUID) -> list[TransferMatchOptionVM]:
        options: list[TransferMatchOptionVM] = []
        for suggestion in self.transfer_suggestions.get(row_id, []):
            candidate = getattr(suggestion, "raw_transaction", None)
            if candidate is None:
                continue
            candidate_id = ReviewReferenceResolver.required_id(candidate)
            account_id = self.raw_transaction_account_id(candidate)
            account_name = self.raw_transaction_account_name(candidate)
            date = getattr(candidate, "operation_date", None) or getattr(
                candidate,
                "operation_date_raw",
                None,
            )
            amount = getattr(candidate, "amount", "")
            currency = getattr(candidate, "currency", "") or ""
            row_index = getattr(candidate, "row_index", "")
            day_distance = getattr(suggestion, "day_distance", "")
            description = (
                getattr(candidate, "description_normalized", None)
                or getattr(candidate, "description_raw", None)
                or ""
            )
            options.append(
                TransferMatchOptionVM(
                    value=f"raw:{candidate_id}",
                    account_id=account_id,
                    label=(
                        f"строка выписки · {self.date_labeler.date(date)} · "
                        f"{amount} {currency} · "
                        f"{account_name} · строка {row_index} · {day_distance} дн. · "
                        f"{description}"
                    ),
                )
            )
        return options

    def raw_transaction_account_id(self, raw_transaction: object) -> UUID | None:
        direct_account_id = getattr(raw_transaction, "account_id", None)
        if direct_account_id is not None:
            return direct_account_id
        document = getattr(raw_transaction, "uploaded_document", None)
        return getattr(document, "account_id", None)

    def raw_transaction_account_name(self, raw_transaction: object) -> str:
        account = getattr(raw_transaction, "account", None)
        if account is not None:
            return str(getattr(account, "name", "счет не найден"))
        document = getattr(raw_transaction, "uploaded_document", None)
        document_account = getattr(document, "account", None)
        if document_account is not None:
            return str(getattr(document_account, "name", "счет не найден"))
        return "счет не найден"

    def existing_transfer_match_options(self, row_id: UUID) -> list[TransferMatchOptionVM]:
        options: list[TransferMatchOptionVM] = []
        for suggestion in self.existing_transfer_suggestions.get(row_id, []):
            operation = getattr(suggestion, "operation", None)
            if operation is None:
                continue
            operation_id = ReviewReferenceResolver.required_id(operation)
            account_entry = getattr(suggestion, "account_entry", None)
            counterparty = getattr(suggestion, "counterparty_entry", None)
            counterparty_account = getattr(counterparty, "account", None)
            counterparty_account_name = getattr(counterparty_account, "name", "счет не найден")
            date = getattr(operation, "operation_date", None)
            amount = getattr(account_entry, "amount", "") if account_entry else ""
            currency = getattr(account_entry, "currency", "") if account_entry else ""
            day_distance = getattr(suggestion, "day_distance", "")
            description = getattr(operation, "description", None) or "ручной перевод"
            options.append(
                TransferMatchOptionVM(
                    value=f"operation:{operation_id}",
                    account_id=getattr(counterparty, "account_id", None),
                    label=(
                        f"ручной перевод · {self.date_labeler.date(date)} · "
                        f"{amount} {currency} · "
                        f"{counterparty_account_name} · {day_distance} дн. · {description}"
                    ),
                )
            )
        return options
