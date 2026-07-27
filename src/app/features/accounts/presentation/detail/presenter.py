from decimal import Decimal
from typing import Final

from app.features.accounts.presentation.detail.models import (
    AccountDetailAccountVM,
    AccountDetailMetricVM,
    AccountDetailPageVM,
    AccountDetailPresenterInput,
    AccountMovementActionVM,
    AccountMovementBadgeVM,
    AccountMovementDrawerVM,
    AccountMovementEditPanelVM,
    AccountMovementMetaVM,
    AccountMovementVM,
    OperationResultVM,
)
from app.features.ledger.application.account_ledger import (
    AccountLedgerDetailView,
    AccountLedgerEntryView,
    AccountView,
    OperationRefMoneyEntryView,
    OperationRefView,
    RawTransactionLinkView,
)
from app.features.ledger.domain.types import imported_operation_actions
from app.features.ledger.models import OperationSource, OperationStatus, OperationType
from app.templating import date_ru, ru_label

DEFAULT_STATUS_FILTER: Final = OperationStatus.CONFIRMED
IMPORTANT_STATUSES: Final = {
    OperationStatus.DRAFT,
    OperationStatus.NEEDS_REVIEW,
    OperationStatus.IGNORED,
    OperationStatus.DUPLICATE,
}


class AccountDetailPresenter:
    @staticmethod
    def build(
        detail: AccountLedgerDetailView,
        presenter_input: AccountDetailPresenterInput,
    ) -> AccountDetailPageVM:
        return AccountDetailPageVM(
            account=AccountDetailPresenter._account(detail),
            balance=detail.balance,
            metrics=AccountDetailPresenter._metrics(detail),
            movements=[
                AccountDetailPresenter._movement(detail.account, entry, presenter_input)
                for entry in detail.entries
            ],
            filters_active=AccountDetailPresenter._filters_active(presenter_input),
            page=detail.page,
        )

    @staticmethod
    def build_movement(
        account: AccountView,
        entry: AccountLedgerEntryView,
        presenter_input: AccountDetailPresenterInput,
    ) -> AccountMovementVM:
        return AccountDetailPresenter._movement(account, entry, presenter_input)

    @staticmethod
    def _account(detail: AccountLedgerDetailView) -> AccountDetailAccountVM:
        return AccountDetailAccountVM(
            id=detail.account.id,
            name=detail.account.name,
            type=detail.account.type,
            type_label=ru_label(detail.account.type),
            currency=detail.account.currency,
            is_active=detail.account.is_active,
            initial_balance=detail.account.initial_balance,
        )

    @staticmethod
    def _metrics(detail: AccountLedgerDetailView) -> list[AccountDetailMetricVM]:
        return [
            AccountDetailMetricVM("баланс", f"{detail.balance} {detail.account.currency}"),
            AccountDetailMetricVM(
                "начальный",
                f"{detail.account.initial_balance} {detail.account.currency}",
            ),
            AccountDetailMetricVM("проводки", str(detail.page.total)),
        ]

    @staticmethod
    def _movement(
        account: AccountView,
        entry: AccountLedgerEntryView,
        presenter_input: AccountDetailPresenterInput,
    ) -> AccountMovementVM:
        source_url = AccountDetailPresenter._source_url(entry.operation)
        edit_form_url = AccountDetailPresenter._edit_form_url(
            account.id,
            entry.operation,
            presenter_input,
        )
        primary_action = AccountDetailPresenter._primary_action(
            entry,
            edit_form_url,
            presenter_input,
        )
        secondary_actions = AccountDetailPresenter._secondary_actions(entry, source_url)
        return AccountMovementVM(
            id=f"operation-{entry.operation_id}",
            operation_id=entry.operation_id,
            tone=entry.operation.type.value,
            amount=entry.amount,
            amount_direction=entry.amount_direction,
            currency=entry.currency,
            date_label=date_ru(entry.operation.operation_date),
            badges=AccountDetailPresenter._badges(entry.operation),
            description=entry.operation.description or "Без описания",
            meta=AccountDetailPresenter._meta(entry.operation, account.name),
            result=AccountDetailPresenter._result(entry.operation),
            primary_action=primary_action,
            secondary_actions=secondary_actions,
            edit_panel_id=(
                f"account-movement-edit-panel-{entry.operation_id}"
                if edit_form_url is not None
                else None
            ),
            edit_form_url=edit_form_url,
            technical_label=(
                f"ID {entry.operation_id} · {source_context_label(entry.operation.source)}"
            ),
        )

    @staticmethod
    def build_edit_panel(
        *,
        account_id: object,
        operation: OperationRefView,
    ) -> AccountMovementEditPanelVM:
        return AccountMovementEditPanelVM(
            drawer=AccountDetailPresenter._drawer(
                account_id=account_id,
                operation=operation,
                source_url=AccountDetailPresenter._source_url(operation),
            )
        )

    @staticmethod
    def _badges(operation: OperationRefView) -> list[AccountMovementBadgeVM]:
        badges: list[AccountMovementBadgeVM] = []
        if operation.status in IMPORTANT_STATUSES:
            badges.append(
                AccountMovementBadgeVM(
                    ru_label(operation.status),
                    operation.status.value,
                )
            )
        if (
            operation.type in {OperationType.INCOME, OperationType.EXPENSE}
            and operation.category is None
        ):
            badges.append(AccountMovementBadgeVM("без категории", "warning"))
        return badges

    @staticmethod
    def _meta(operation: OperationRefView, account_name: str) -> list[AccountMovementMetaVM]:
        if operation.type == OperationType.TRANSFER:
            route = transfer_route(operation)
            return [
                AccountMovementMetaVM(
                    route or "маршрут перевода не определен",
                    "classification",
                ),
                AccountMovementMetaVM(account_name),
                AccountMovementMetaVM("не влияет на прибыль"),
                AccountMovementMetaVM(ru_label(operation.status)),
            ]

        meta: list[AccountMovementMetaVM] = []
        if operation.category is not None:
            meta.append(AccountMovementMetaVM(operation.category.name, "classification"))
        else:
            meta.append(AccountMovementMetaVM("Без категории", "warning"))
        if operation.property is not None:
            meta.append(AccountMovementMetaVM(operation.property.name))
        meta.append(AccountMovementMetaVM(account_name))
        meta.append(AccountMovementMetaVM(ru_label(operation.status)))
        return meta

    @staticmethod
    def _result(operation: OperationRefView) -> OperationResultVM:
        eyebrow = f"{ru_label(operation.type)} · {ru_label(operation.status)}"
        if operation.type == OperationType.TRANSFER:
            return OperationResultVM(
                eyebrow=eyebrow,
                title=transfer_route(operation) or "Перевод",
                tone=operation.type.value,
                detail="не влияет на прибыль",
            )
        if operation.category is not None:
            title = operation.category.name
        elif operation.source == OperationSource.SYSTEM:
            title = "только чтение"
        else:
            title = "Без категории"
        return OperationResultVM(
            eyebrow=eyebrow,
            title=title,
            tone=operation.type.value,
        )

    @staticmethod
    def _primary_action(
        entry: AccountLedgerEntryView,
        edit_form_url: str | None,
        presenter_input: AccountDetailPresenterInput,
    ) -> AccountMovementActionVM | None:
        if not presenter_input.can_write:
            return None
        if edit_form_url is not None:
            return AccountMovementActionVM(
                id="edit",
                label="исправить",
                icon="settings",
                placement="primary",
                action_type="drawer_toggle",
            )
        if entry.operation.source == OperationSource.MANUAL:
            return AccountMovementActionVM(
                id="edit",
                label="редактировать",
                icon="plus",
                placement="primary",
                action_type="link",
                url=f"/app/ledger/manual?operation_id={entry.operation_id}#operation-{entry.operation_id}",
            )
        if entry.operation.source == OperationSource.SYSTEM:
            return AccountMovementActionVM(
                id="readonly",
                label="только чтение",
                icon="file-text",
                placement="secondary",
                action_type="readonly",
            )
        return None

    @staticmethod
    def _secondary_actions(
        entry: AccountLedgerEntryView,
        source_url: str | None,
    ) -> list[AccountMovementActionVM]:
        if source_url is not None:
            return [
                AccountMovementActionVM(
                    id="source",
                    label="строка импорта",
                    icon="refresh",
                    placement="secondary",
                    action_type="link",
                    url=source_url,
                )
            ]
        if entry.operation.source == OperationSource.BANK_PDF:
            return [
                AccountMovementActionVM(
                    id="source",
                    label="найти импорт",
                    icon="refresh",
                    placement="secondary",
                    action_type="link",
                    url="/app/imports",
                )
            ]
        return []

    @staticmethod
    def _drawer(
        *,
        account_id: object,
        operation: OperationRefView,
        source_url: str | None,
    ) -> AccountMovementDrawerVM:
        return AccountMovementDrawerVM(
            kind="импорт",
            title="Исправить операцию",
            form_action=f"/accounts/{account_id}/operations/{operation.id}/review-fields",
            version=operation.version,
            description=operation.description or "",
            category_id=operation.category.id if operation.category else None,
            property_id=operation.property.id if operation.property else None,
            source_url=source_url,
        )

    @staticmethod
    def _edit_form_url(
        account_id: object,
        operation: OperationRefView,
        presenter_input: AccountDetailPresenterInput,
    ) -> str | None:
        if (
            not presenter_input.can_write
            or operation.source != OperationSource.BANK_PDF
            or not imported_operation_actions(operation.status).can_edit_review_fields
        ):
            return None
        return f"/accounts/{account_id}/operations/{operation.id}/review-fields/edit"

    @staticmethod
    def _source_url(operation: OperationRefView) -> str | None:
        raw_link = first_raw_link(operation.raw_transactions)
        if raw_link is None:
            return None
        return f"/app/imports/documents/{raw_link.uploaded_document_id}/review#raw-{raw_link.id}"

    @staticmethod
    def _filters_active(presenter_input: AccountDetailPresenterInput) -> bool:
        return any(
            (
                presenter_input.filters_date_from,
                presenter_input.filters_date_to,
                presenter_input.filters_source,
                presenter_input.filters_operation_type,
                presenter_input.filters_status
                and presenter_input.filters_status != DEFAULT_STATUS_FILTER,
                presenter_input.filters_category_id,
                presenter_input.filters_property_id,
                presenter_input.filters_search,
            )
        )


def transfer_route(operation: OperationRefView) -> str | None:
    from_entry = first_negative_entry(operation.money_entries)
    to_entry = first_positive_entry(operation.money_entries)
    if from_entry is None or to_entry is None:
        return None
    return f"{account_name(from_entry)} -> {account_name(to_entry)}"


def account_name(entry: OperationRefMoneyEntryView) -> str:
    return entry.account.name if entry.account is not None else "счет не найден"


def first_negative_entry(
    entries: list[OperationRefMoneyEntryView],
) -> OperationRefMoneyEntryView | None:
    return next((entry for entry in entries if entry.amount < Decimal("0")), None)


def first_positive_entry(
    entries: list[OperationRefMoneyEntryView],
) -> OperationRefMoneyEntryView | None:
    return next((entry for entry in entries if entry.amount > Decimal("0")), None)


def first_raw_link(raw_transactions: list[RawTransactionLinkView]) -> RawTransactionLinkView | None:
    return raw_transactions[0] if raw_transactions else None


def source_context_label(source: OperationSource) -> str:
    if source == OperationSource.BANK_PDF:
        return "из выписки"
    if source == OperationSource.MANUAL:
        return "ручная операция"
    if source == OperationSource.SYSTEM:
        return "системная операция"
    return ru_label(source)
