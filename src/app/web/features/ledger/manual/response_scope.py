from enum import StrEnum
from uuid import UUID

from app.features.ledger.application.listing import ManualOperationFilters
from app.features.ledger.mapping.dto import ManualOperationView


class ManualLedgerUpdateScope(StrEnum):
    REPLACE_ROW = "replace_row"
    REPLACE_LIST = "replace_list"


class ManualLedgerUpdateResponseScope:
    def resolve(
        self,
        *,
        previous: ManualOperationView,
        updated: ManualOperationView,
        filters: ManualOperationFilters,
    ) -> ManualLedgerUpdateScope:
        if previous.operation_date != updated.operation_date:
            return ManualLedgerUpdateScope.REPLACE_LIST
        if self._matches(previous, filters) != self._matches(updated, filters):
            return ManualLedgerUpdateScope.REPLACE_LIST
        return ManualLedgerUpdateScope.REPLACE_ROW

    def _matches(
        self,
        operation: ManualOperationView,
        filters: ManualOperationFilters,
    ) -> bool:
        if filters.date_from is not None and operation.operation_date < filters.date_from:
            return False
        if filters.date_to is not None and operation.operation_date > filters.date_to:
            return False
        if filters.operation_type is not None and operation.type != filters.operation_type:
            return False
        if filters.status is not None and operation.status != filters.status:
            return False
        if filters.account_id is not None and filters.account_id not in self._account_ids(
            operation
        ):
            return False
        if filters.category_id is not None and operation.category_id != filters.category_id:
            return False
        if filters.property_id is not None and operation.property_id != filters.property_id:
            return False
        if (
            filters.search
            and filters.search.casefold() not in (operation.description or "").casefold()
        ):
            return False
        return True

    def _account_ids(self, operation: ManualOperationView) -> set[UUID]:
        return {
            entry.account_id
            for entry in (
                operation.primary_entry,
                operation.source_entry,
                operation.destination_entry,
            )
            if entry is not None
        }
