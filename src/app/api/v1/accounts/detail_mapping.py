from decimal import Decimal

from app.api.v1.accounts.schemas import (
    AccountDetailAccountApiResponse,
    AccountDetailApiResponse,
    AccountDetailCapabilitiesApiResponse,
    AccountDetailFilterOptionsApiResponse,
    AccountDetailNamedReferenceApiResponse,
    AccountDetailPaginationApiResponse,
    AccountMovementApiResponse,
    AccountMovementCapabilitiesApiResponse,
    AccountMovementSourceTargetApiResponse,
)
from app.features.accounts.models import AccountType
from app.features.ledger.application.account_ledger import (
    AccountLedgerDetailView,
    AccountLedgerEntryView,
    OperationRefView,
)
from app.features.ledger.application.manual_operations import ManualLedgerReferenceOptionsDto
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType

PER_PAGE_OPTIONS = [25, 50, 100, 200]


class AccountDetailResponseMapper:
    @staticmethod
    def response(
        detail: AccountLedgerDetailView,
        references: ManualLedgerReferenceOptionsDto,
        *,
        can_write: bool,
    ) -> AccountDetailApiResponse:
        return AccountDetailApiResponse(
            account=AccountDetailAccountApiResponse(
                id=detail.account.id,
                name=detail.account.name,
                account_type=detail.account.type,
                currency=detail.account.currency,
                initial_balance=AccountDetailResponseMapper._money(detail.account.initial_balance),
                balance=AccountDetailResponseMapper._money(detail.balance),
                is_active=detail.account.is_active,
                updated_at=detail.account.updated_at,
                capabilities=AccountDetailCapabilitiesApiResponse(
                    can_update=can_write,
                    can_archive=can_write and detail.account.is_active,
                    can_restore=can_write and not detail.account.is_active,
                ),
            ),
            items=[
                AccountDetailResponseMapper.movement_response(item, can_write=can_write)
                for item in detail.entries
            ],
            pagination=AccountDetailPaginationApiResponse.model_validate(detail.page),
            filter_options=AccountDetailFilterOptionsApiResponse(
                categories=[
                    AccountDetailNamedReferenceApiResponse.model_validate(item)
                    for item in references.categories
                ],
                properties=[
                    AccountDetailNamedReferenceApiResponse.model_validate(item)
                    for item in references.properties
                ],
                per_page=PER_PAGE_OPTIONS,
            ),
        )

    @staticmethod
    def movement_response(
        entry: AccountLedgerEntryView,
        *,
        can_write: bool,
    ) -> AccountMovementApiResponse:
        operation = entry.operation
        return AccountMovementApiResponse(
            operation_id=entry.operation_id,
            version=operation.version,
            operation_type=operation.type,
            operation_date=operation.operation_date,
            description=operation.description or "",
            status=operation.status,
            source=operation.source,
            amount=AccountDetailResponseMapper._money(entry.amount),
            currency=entry.currency,
            category=(
                AccountDetailNamedReferenceApiResponse.model_validate(operation.category)
                if operation.category
                else None
            ),
            property=(
                AccountDetailNamedReferenceApiResponse.model_validate(operation.property)
                if operation.property
                else None
            ),
            transfer_route=AccountDetailResponseMapper._transfer_route(operation),
            source_target=AccountDetailResponseMapper._source_target(operation),
            capabilities=AccountDetailResponseMapper._movement_capabilities(
                operation,
                can_write=can_write,
            ),
        )

    @staticmethod
    def _movement_capabilities(
        operation: OperationRefView,
        *,
        can_write: bool,
    ) -> AccountMovementCapabilitiesApiResponse:
        if not can_write:
            return AccountMovementCapabilitiesApiResponse(
                can_edit_review_fields=False,
                readonly_reason_code="financial_write_forbidden",
            )
        if operation.source != OperationSource.BANK_PDF:
            return AccountMovementCapabilitiesApiResponse(
                can_edit_review_fields=False,
                readonly_reason_code="imported_operation_only",
            )
        if operation.status != OperationStatus.CONFIRMED:
            return AccountMovementCapabilitiesApiResponse(
                can_edit_review_fields=False,
                readonly_reason_code="operation_not_confirmed",
            )
        return AccountMovementCapabilitiesApiResponse(
            can_edit_review_fields=True,
            readonly_reason_code=None,
        )

    @staticmethod
    def _source_target(operation: OperationRefView) -> AccountMovementSourceTargetApiResponse:
        if operation.source == OperationSource.MANUAL:
            return AccountMovementSourceTargetApiResponse(kind="manual")
        if operation.source == OperationSource.BANK_PDF:
            raw = operation.raw_transactions[0] if operation.raw_transactions else None
            return AccountMovementSourceTargetApiResponse(
                kind="import",
                uploaded_document_id=raw.uploaded_document_id if raw else None,
                raw_transaction_id=raw.id if raw else None,
            )
        if operation.source == OperationSource.DEBT:
            debt_entry = next(
                (
                    item
                    for item in operation.money_entries
                    if item.account is not None and item.account.type is AccountType.DEBT
                ),
                None,
            )
            return AccountMovementSourceTargetApiResponse(
                kind="debt",
                debt_account_id=debt_entry.account_id if debt_entry else None,
            )
        return AccountMovementSourceTargetApiResponse(kind="system")

    @staticmethod
    def _transfer_route(operation: OperationRefView) -> str | None:
        if operation.type != OperationType.TRANSFER:
            return None
        negative = next((item for item in operation.money_entries if item.amount < 0), None)
        positive = next((item for item in operation.money_entries if item.amount > 0), None)
        if negative is None or positive is None:
            return None
        source = negative.account.name if negative.account else "Счёт не найден"
        destination = positive.account.name if positive.account else "Счёт не найден"
        return f"{source} → {destination}"

    @staticmethod
    def _money(value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), "f")
