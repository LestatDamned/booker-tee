from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError

from app.api.schemas import ApiRequestModel
from app.features.ledger.domain.types import OperationType


class ManualOperationCreateApiRequestBase(ApiRequestModel):
    amount: str
    operation_date: date
    description: str = ""

    @field_validator("amount")
    @classmethod
    def require_positive_decimal_string(cls, amount: str) -> str:
        normalized = amount.strip().replace(",", ".")
        try:
            decimal_amount = Decimal(normalized)
        except InvalidOperation as error:
            raise PydanticCustomError(
                "decimal_amount",
                "Введите корректную сумму.",
            ) from error
        if not decimal_amount.is_finite() or decimal_amount <= Decimal("0"):
            raise PydanticCustomError(
                "positive_amount",
                "Сумма должна быть больше нуля.",
            )
        return normalized

    @property
    def decimal_amount(self) -> Decimal:
        return Decimal(self.amount)


class ManualIncomeExpenseCreateApiRequest(ManualOperationCreateApiRequestBase):
    operation_type: Literal[OperationType.INCOME, OperationType.EXPENSE]
    account_id: UUID
    category_id: UUID | None = None
    property_id: UUID | None = None


class ManualTransferCreateApiRequest(ManualOperationCreateApiRequestBase):
    operation_type: Literal[OperationType.TRANSFER]
    source_account_id: UUID
    destination_account_id: UUID


ManualOperationCreateApiRequest = Annotated[
    ManualIncomeExpenseCreateApiRequest | ManualTransferCreateApiRequest,
    Field(discriminator="operation_type"),
]


class ManualOperationUpdateApiRequestBase(ManualOperationCreateApiRequestBase):
    version: int

    @field_validator("version")
    @classmethod
    def require_current_version(cls, version: int) -> int:
        if version < 1:
            raise PydanticCustomError(
                "current_operation_version",
                "Загрузите актуальную версию операции.",
            )
        return version


class ManualIncomeExpenseUpdateApiRequest(ManualOperationUpdateApiRequestBase):
    operation_type: Literal[OperationType.INCOME, OperationType.EXPENSE]
    account_id: UUID
    category_id: UUID | None = None
    property_id: UUID | None = None


class ManualTransferUpdateApiRequest(ManualOperationUpdateApiRequestBase):
    operation_type: Literal[OperationType.TRANSFER]
    source_account_id: UUID
    destination_account_id: UUID


ManualOperationUpdateApiRequest = Annotated[
    ManualIncomeExpenseUpdateApiRequest | ManualTransferUpdateApiRequest,
    Field(discriminator="operation_type"),
]


class ManualOperationLifecycleApiRequest(ApiRequestModel):
    version: int = Field(ge=1)
