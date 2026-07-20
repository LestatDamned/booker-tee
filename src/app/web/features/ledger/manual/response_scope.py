from enum import StrEnum

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
        if previous.operation_date != updated.operation_date or filters.is_active:
            return ManualLedgerUpdateScope.REPLACE_LIST
        return ManualLedgerUpdateScope.REPLACE_ROW
