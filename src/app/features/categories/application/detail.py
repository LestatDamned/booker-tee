from collections.abc import Sequence
from datetime import date
from typing import Protocol
from uuid import UUID

from app.features.categories.application.directory import category_kind_options, category_summary
from app.features.categories.schemas import (
    CategoryDetailDto,
    CategoryDetailFiltersDto,
    CategoryKindChangeImpactDto,
    CategoryMoneySummaryDto,
    CategoryOperationDto,
    CategoryOperationPageDto,
    CategoryRulePreviewDto,
    CategoryRulePreviewItemDto,
)
from app.features.categories.service import CategoryManagementRow
from app.features.ledger.domain.types import OperationType
from app.features.ledger.models import Operation
from app.features.reports.service import operation_signed_total, summarize_income_expense
from app.features.transaction_rules.models import TransactionRule

DEFAULT_CATEGORY_OPERATION_PAGE_SIZE = 20
MAX_CATEGORY_OPERATION_PAGE_SIZE = 100
CATEGORY_RULE_PREVIEW_LIMIT = 5


class CategoryDetailNotFoundError(LookupError):
    pass


class CategoryDetailFilterError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CategoryDetailSource(Protocol):
    async def get_management_row(
        self,
        workspace_id: UUID,
        category_id: UUID,
    ) -> CategoryManagementRow | None: ...


class CategoryOperationSource(Protocol):
    async def list_confirmed_operations(
        self,
        *,
        workspace_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: UUID | None = None,
        category_id: UUID | None = None,
        property_id: UUID | None = None,
        currency: str | None = None,
        operation_type: OperationType | None = None,
    ) -> list[Operation]: ...

    async def list_confirmed_category_operations_page(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        date_from: date | None,
        date_to: date | None,
        currency: str,
        operation_type: OperationType | None,
        search: str | None,
        offset: int,
        limit: int,
    ) -> list[Operation]: ...

    async def count_confirmed_category_operations(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        date_from: date | None,
        date_to: date | None,
        currency: str,
        operation_type: OperationType | None,
        search: str | None,
    ) -> int: ...


class CategoryRuleSource(Protocol):
    async def list_category_preview(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        limit: int,
    ) -> Sequence[TransactionRule]: ...

    async def count_category_rules(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
    ) -> tuple[int, int]: ...


class WorkspaceCurrencySource(Protocol):
    async def list_workspace_currencies(self, workspace_id: UUID) -> list[str]: ...


class CategoryDetailReader:
    def __init__(
        self,
        *,
        categories: CategoryDetailSource,
        currencies: WorkspaceCurrencySource,
        operations: CategoryOperationSource,
        rules: CategoryRuleSource,
    ) -> None:
        self._categories = categories
        self._currencies = currencies
        self._operations = operations
        self._rules = rules

    async def read(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        default_currency: str,
        can_write: bool,
        date_from: date | None = None,
        date_to: date | None = None,
        currency: str | None = None,
        operation_type: OperationType | None = None,
        search: str | None = None,
        operations_page: int = 1,
        operations_page_size: int = DEFAULT_CATEGORY_OPERATION_PAGE_SIZE,
    ) -> CategoryDetailDto:
        self._validate_filters(
            date_from=date_from,
            date_to=date_to,
            operation_type=operation_type,
        )
        row = await self._categories.get_management_row(workspace_id, category_id)
        if row is None:
            raise CategoryDetailNotFoundError

        available_currencies = sorted(
            {
                default_currency.upper(),
                *(
                    item.upper()
                    for item in await self._currencies.list_workspace_currencies(workspace_id)
                ),
            }
        )
        selected_currency = (currency or default_currency).upper()
        if selected_currency not in available_currencies:
            raise CategoryDetailFilterError(
                "invalid_category_currency",
                "Эта валюта недоступна в текущем workspace.",
            )

        filters = CategoryDetailFiltersDto(
            date_from=date_from,
            date_to=date_to,
            currency=selected_currency,
            operation_type=operation_type,
            search=search,
        )
        summary_operations = await self._operations.list_confirmed_operations(
            workspace_id=workspace_id,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            currency=selected_currency,
            operation_type=operation_type,
        )
        profit_operations = [
            operation for operation in summary_operations if operation.affects_profit
        ]
        summary = summarize_income_expense(
            profit_operations,
            currency=selected_currency,
        )
        total = await self._operations.count_confirmed_category_operations(
            workspace_id=workspace_id,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            currency=selected_currency,
            operation_type=operation_type,
            search=search,
        )
        page_operations = await self._operations.list_confirmed_category_operations_page(
            workspace_id=workspace_id,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
            currency=selected_currency,
            operation_type=operation_type,
            search=search,
            offset=(operations_page - 1) * operations_page_size,
            limit=operations_page_size,
        )
        rules = await self._rules.list_category_preview(
            workspace_id=workspace_id,
            category_id=category_id,
            limit=CATEGORY_RULE_PREVIEW_LIMIT,
        )
        rule_total, active_rule_count = await self._rules.count_category_rules(
            workspace_id=workspace_id,
            category_id=category_id,
        )
        total_pages = max(1, (total + operations_page_size - 1) // operations_page_size)
        return CategoryDetailDto(
            category=category_summary(row, can_write=can_write),
            kind_options=category_kind_options(),
            kind_change_impact=CategoryKindChangeImpactDto(
                existing_operations_unchanged=True,
                picker_compatibility_may_change=True,
                operation_count=row.operation_count,
                rule_count=row.rule_count,
                requires_confirmation=(row.operation_count + row.rule_count) > 0,
            ),
            applied_filters=filters,
            available_currencies=available_currencies,
            summary=CategoryMoneySummaryDto(
                currency=selected_currency,
                income=summary.income,
                expense=summary.expense,
                profit=summary.profit,
            ),
            operations=CategoryOperationPageDto(
                items=[
                    category_operation(operation, currency=selected_currency)
                    for operation in page_operations
                ],
                page=operations_page,
                page_size=operations_page_size,
                total=total,
                total_pages=total_pages,
                has_previous=operations_page > 1,
                has_next=operations_page < total_pages,
            ),
            rules=CategoryRulePreviewDto(
                items=[category_rule(rule) for rule in rules],
                total=rule_total,
                active_count=active_rule_count,
            ),
        )

    @staticmethod
    def _validate_filters(
        *,
        date_from: date | None,
        date_to: date | None,
        operation_type: OperationType | None,
    ) -> None:
        if date_from and date_to and date_from > date_to:
            raise CategoryDetailFilterError(
                "invalid_category_date_range",
                "Начало периода не может быть позже конца периода.",
            )
        if operation_type not in {None, OperationType.INCOME, OperationType.EXPENSE}:
            raise CategoryDetailFilterError(
                "invalid_category_operation_type",
                "Для detail доступны только доходы или расходы.",
            )


def category_operation(operation: Operation, *, currency: str) -> CategoryOperationDto:
    account_names = list(
        dict.fromkeys(
            entry.account.name for entry in operation.money_entries if entry.currency == currency
        )
    )
    return CategoryOperationDto(
        operation_id=operation.id,
        operation_date=operation.operation_date,
        operation_type=operation.type,
        description=operation.description or "Без описания",
        account_name=" → ".join(account_names) or "Счёт не указан",
        property_id=operation.property.id if operation.property else None,
        property_name=operation.property.name if operation.property else None,
        signed_amount=operation_signed_total(operation, currency=currency),
        currency=currency,
    )


def category_rule(rule: TransactionRule) -> CategoryRulePreviewItemDto:
    return CategoryRulePreviewItemDto(
        id=rule.id,
        name=rule.name,
        is_active=rule.is_active,
        priority=rule.priority,
        pattern=rule.pattern,
        match_type=rule.match_type,
        application_mode=rule.application_mode,
    )
