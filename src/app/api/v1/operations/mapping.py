from decimal import Decimal

from app.api.v1.operations.schemas import (
    OperationApiResponse,
    OperationCapabilitiesApiResponse,
    OperationMoneyApiResponse,
    OperationsCapabilitiesApiResponse,
    OperationsFilterOptionsApiResponse,
    OperationsListApiResponse,
    OperationsPaginationApiResponse,
)
from app.features.ledger.domain.types import OperationSource
from app.features.ledger.schemas.listing import LedgerPage
from app.features.ledger.schemas.manual import ManualLedgerReferenceOptionsDto
from app.features.ledger.schemas.operations import OperationReadDto

READONLY_REASON = "Операции доступны только для просмотра согласно вашей роли."
PER_PAGE_OPTIONS = [25, 50, 100, 200]
SOURCE_OPTIONS = [
    OperationSource.MANUAL,
    OperationSource.BANK_PDF,
    OperationSource.DEBT,
    OperationSource.SYSTEM,
]


class OperationsResponseMapper:
    @staticmethod
    def list_response(
        *,
        operations: list[OperationReadDto],
        page: LedgerPage,
        references: ManualLedgerReferenceOptionsDto,
        can_write: bool,
        target_operation: OperationReadDto | None,
    ) -> OperationsListApiResponse:
        return OperationsListApiResponse(
            items=[OperationsResponseMapper.operation(item) for item in operations],
            pagination=OperationsPaginationApiResponse.model_validate(page),
            filter_options=OperationsFilterOptionsApiResponse.model_validate(
                {
                    "accounts": references.accounts,
                    "categories": references.categories,
                    "properties": references.properties,
                    "sources": SOURCE_OPTIONS,
                    "per_page": PER_PAGE_OPTIONS,
                }
            ),
            capabilities=OperationsCapabilitiesApiResponse(
                can_create=can_write,
                readonly_reason=None if can_write else READONLY_REASON,
            ),
            target_operation_id=target_operation.id if target_operation else None,
            target_operation=(
                OperationsResponseMapper.operation(target_operation) if target_operation else None
            ),
        )

    @staticmethod
    def operation(operation: OperationReadDto) -> OperationApiResponse:
        money = operation.money
        return OperationApiResponse.model_validate(
            {
                **operation.model_dump(),
                "description": operation.description or "",
                "money": (
                    OperationMoneyApiResponse(
                        amount=OperationsResponseMapper._money(money.amount),
                        currency=money.currency,
                    )
                    if money
                    else None
                ),
                "capabilities": OperationCapabilitiesApiResponse.model_validate(
                    operation.capabilities
                ),
            }
        )

    @staticmethod
    def _money(value: Decimal) -> str:
        return format(value.quantize(Decimal("0.01")), "f")
