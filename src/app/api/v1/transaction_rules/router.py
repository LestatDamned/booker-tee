from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import api_error_responses
from app.api.v1.transaction_rules.dependencies import (
    get_transaction_rule_directory_reader,
)
from app.api.v1.transaction_rules.parameters import (
    TransactionRuleDirectoryParameters,
    parse_transaction_rule_directory_parameters,
)
from app.api.v1.transaction_rules.schemas import TransactionRuleDirectoryApiResponse
from app.features.transaction_rules.application.directory import (
    TransactionRuleDirectoryReader,
)
from app.features.workspaces.permissions import can_write_financial_data

router = APIRouter(prefix="/transaction-rules", tags=["transaction-rules"])


@router.get(
    "",
    response_model=TransactionRuleDirectoryApiResponse,
    responses=api_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def list_transaction_rules(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    parameters: Annotated[
        TransactionRuleDirectoryParameters,
        Depends(parse_transaction_rule_directory_parameters),
    ],
    reader: Annotated[
        TransactionRuleDirectoryReader,
        Depends(get_transaction_rule_directory_reader),
    ],
) -> TransactionRuleDirectoryApiResponse:
    directory = await reader.read(
        workspace_id=context.workspace.workspace.id,
        can_write=can_write_financial_data(context.workspace.membership),
        search=parameters.search,
        category_id=parameters.category_id,
        status=parameters.status,
        page=parameters.page,
        page_size=parameters.page_size,
    )
    return TransactionRuleDirectoryApiResponse.model_validate(directory)
