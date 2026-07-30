from app.features.chat_integrations.errors import ChatManualOperationError
from app.features.chat_integrations.use_cases.manual.dto import ChatManualOperationConfirmation
from app.features.chat_integrations.use_cases.manual.state_reader import (
    ChatManualOperationStateReader,
)
from app.features.ledger.application.manual_mutations import ManualOperationWriter
from app.features.ledger.domain.types import OperationType
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.models import Operation
from app.features.ledger.schemas.manual import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
)
from app.features.workspaces.service import WorkspaceContext


class ChatManualOperationPoster:
    def __init__(self, manual_operations: ManualOperationWriter) -> None:
        self.manual_operations = manual_operations

    async def post(
        self,
        *,
        context: WorkspaceContext,
        payload: dict[str, object],
        confirmation: ChatManualOperationConfirmation,
    ) -> Operation:
        try:
            if confirmation.operation_type == OperationType.TRANSFER:
                return await self._post_transfer(
                    context=context,
                    payload=payload,
                    confirmation=confirmation,
                )

            return await self._post_income_expense(
                context=context,
                payload=payload,
                confirmation=confirmation,
            )
        except (LedgerPostingError, ValueError) as exc:
            raise ChatManualOperationError(str(exc)) from exc

    async def _post_transfer(
        self,
        *,
        context: WorkspaceContext,
        payload: dict[str, object],
        confirmation: ChatManualOperationConfirmation,
    ) -> Operation:
        return await self.manual_operations.create_transfer(
            context=context,
            command=CreateManualTransferCommand(
                source_account_id=ChatManualOperationStateReader.read_required_uuid(
                    payload,
                    "source_account_id",
                ),
                destination_account_id=ChatManualOperationStateReader.read_required_uuid(
                    payload,
                    "destination_account_id",
                ),
                amount=confirmation.amount,
                operation_date=confirmation.operation_date,
                description=confirmation.description,
            ),
        )

    async def _post_income_expense(
        self,
        *,
        context: WorkspaceContext,
        payload: dict[str, object],
        confirmation: ChatManualOperationConfirmation,
    ) -> Operation:
        return await self.manual_operations.create_income_expense(
            context=context,
            command=CreateManualIncomeExpenseCommand(
                operation_type=confirmation.operation_type,
                account_id=ChatManualOperationStateReader.read_required_uuid(
                    payload,
                    "account_id",
                ),
                amount=confirmation.amount,
                operation_date=confirmation.operation_date,
                description=confirmation.description,
                category_id=ChatManualOperationStateReader.read_optional_uuid(
                    payload,
                    "category_id",
                ),
                property_id=None,
            ),
        )
