from decimal import Decimal
from uuid import UUID

from app.api.v1.debts.schemas import (
    AddExistingDebtApiRequest,
    DebtCapabilitiesApiResponse,
    DebtCreateApiRequest,
    DebtCurrencyTotalsApiResponse,
    DebtDetailApiResponse,
    DebtPaymentHistoryItemApiResponse,
    DebtPaymentHistoryPageApiResponse,
    DebtPaymentOperationApiResponse,
    DebtPaymentTotalsApiResponse,
    DebtPortfolioApiResponse,
    DebtPortfolioCapabilitiesApiResponse,
    DebtSummaryApiResponse,
    GiveLoanApiRequest,
    RecordDebtPaymentApiRequest,
    TakeLoanApiRequest,
    UpdateDebtApiRequest,
)
from app.features.debts.schemas import (
    AddExistingDebtCommand,
    DebtCreateCommand,
    DebtDetailDto,
    DebtPaymentHistoryItemDto,
    DebtPaymentOperationDto,
    DebtPortfolioDto,
    DebtSummaryDto,
    GiveLoanCommand,
    OpenCreditCardCommand,
    RecordDebtPaymentCommand,
    TakeLoanCommand,
    UpdateDebtCommand,
)


class DebtRequestMapper:
    @staticmethod
    def to_create_command(
        request: DebtCreateApiRequest,
        *,
        idempotency_key: UUID,
    ) -> DebtCreateCommand:
        if isinstance(request, AddExistingDebtApiRequest):
            return AddExistingDebtCommand(
                name=request.name,
                kind=request.kind,
                currency=request.currency,
                opening_balance=Decimal(request.opening_balance),
                original_principal=Decimal(request.original_principal),
                opened_on=request.opened_on,
                maturity_date=request.maturity_date,
                notes=request.notes,
                idempotency_key=idempotency_key,
            )
        if isinstance(request, GiveLoanApiRequest):
            return GiveLoanCommand(
                name=request.name,
                currency=request.currency,
                amount=Decimal(request.amount),
                funding_account_id=request.funding_account_id,
                operation_date=request.operation_date,
                opened_on=request.opened_on,
                maturity_date=request.maturity_date,
                description=request.description,
                notes=request.notes,
                idempotency_key=idempotency_key,
            )
        if isinstance(request, TakeLoanApiRequest):
            return TakeLoanCommand(
                name=request.name,
                kind=request.kind,
                currency=request.currency,
                amount=Decimal(request.amount),
                receiving_account_id=request.receiving_account_id,
                operation_date=request.operation_date,
                opened_on=request.opened_on,
                maturity_date=request.maturity_date,
                description=request.description,
                notes=request.notes,
                idempotency_key=idempotency_key,
            )
        return OpenCreditCardCommand(
            name=request.name,
            currency=request.currency,
            credit_limit=Decimal(request.credit_limit),
            opening_debt=Decimal(request.opening_debt),
            opened_on=request.opened_on,
            notes=request.notes,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def to_payment_command(
        debt_account_id: UUID,
        request: RecordDebtPaymentApiRequest,
        *,
        idempotency_key: UUID,
    ) -> RecordDebtPaymentCommand:
        return RecordDebtPaymentCommand(
            debt_account_id=debt_account_id,
            settlement_account_id=request.settlement_account_id,
            principal_amount=request.decimal_principal,
            interest_amount=request.decimal_interest,
            operation_date=request.operation_date,
            interest_category_id=request.interest_category_id,
            description=request.description,
            notes=request.notes,
            idempotency_key=idempotency_key,
        )

    @staticmethod
    def to_update_command(
        debt_account_id: UUID,
        request: UpdateDebtApiRequest,
    ) -> UpdateDebtCommand:
        return UpdateDebtCommand(
            debt_account_id=debt_account_id,
            name=request.name,
            opened_on=request.opened_on,
            maturity_date=request.maturity_date,
            credit_limit=(
                Decimal(request.credit_limit) if request.credit_limit is not None else None
            ),
            notes=request.notes,
            expected_updated_at=request.expected_updated_at,
        )


class DebtResponseMapper:
    @staticmethod
    def portfolio(portfolio: DebtPortfolioDto, *, can_write: bool) -> DebtPortfolioApiResponse:
        return DebtPortfolioApiResponse(
            items=[DebtResponseMapper.summary(item) for item in portfolio.items],
            totals=[
                DebtCurrencyTotalsApiResponse(
                    currency=total.currency,
                    receivable=_money(total.receivable),
                    payable=_money(total.payable),
                    net_position=_money(total.net_position),
                )
                for total in portfolio.totals
            ],
            capabilities=DebtPortfolioCapabilitiesApiResponse(
                can_create=can_write,
                readonly_reason_code=None if can_write else "financial_write_forbidden",
            ),
        )

    @staticmethod
    def detail(detail: DebtDetailDto) -> DebtDetailApiResponse:
        return DebtDetailApiResponse(
            debt=DebtResponseMapper.summary(detail.debt),
            notes=detail.notes,
            payment_totals=DebtPaymentTotalsApiResponse(
                principal=_money(detail.payment_totals.principal),
                interest=_money(detail.payment_totals.interest),
            ),
            payments=DebtPaymentHistoryPageApiResponse(
                items=[DebtResponseMapper.payment(item) for item in detail.payments.items],
                page=detail.payments.page,
                page_size=detail.payments.page_size,
                total=detail.payments.total,
                total_pages=detail.payments.total_pages,
                has_previous=detail.payments.has_previous,
                has_next=detail.payments.has_next,
            ),
        )

    @staticmethod
    def summary(summary: DebtSummaryDto) -> DebtSummaryApiResponse:
        return DebtSummaryApiResponse(
            account_id=summary.account_id,
            name=summary.name,
            kind=summary.kind,
            currency=summary.currency,
            balance=_money(summary.balance),
            outstanding=_money(summary.outstanding),
            status=summary.status,
            opened_on=summary.opened_on,
            original_principal=_optional_money(summary.original_principal),
            maturity_date=summary.maturity_date,
            credit_limit=_optional_money(summary.credit_limit),
            available_credit=_optional_money(summary.available_credit),
            is_active=summary.is_active,
            updated_at=summary.updated_at,
            capabilities=DebtCapabilitiesApiResponse.model_validate(summary.capabilities),
        )

    @staticmethod
    def payment(payment: DebtPaymentHistoryItemDto) -> DebtPaymentHistoryItemApiResponse:
        return DebtPaymentHistoryItemApiResponse(
            payment_id=payment.payment_id,
            principal=DebtResponseMapper.payment_operation(payment.principal),
            interest=DebtResponseMapper.payment_operation(payment.interest),
            notes=payment.notes,
            created_at=payment.created_at,
            reversed_at=payment.reversed_at,
            can_undo=payment.can_undo,
        )

    @staticmethod
    def payment_operation(
        operation: DebtPaymentOperationDto | None,
    ) -> DebtPaymentOperationApiResponse | None:
        if operation is None:
            return None
        return DebtPaymentOperationApiResponse(
            operation_id=operation.operation_id,
            version=operation.version,
            operation_date=operation.operation_date,
            operation_type=operation.operation_type,
            status=operation.status,
            description=operation.description,
            amount=_money(operation.amount),
        )


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _optional_money(value: Decimal | None) -> str | None:
    return None if value is None else _money(value)
