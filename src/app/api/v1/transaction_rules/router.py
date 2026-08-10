from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import (
    ApiRequestContext,
    get_api_request_context,
    require_api_financial_write_context,
)
from app.api.errors import api_error_responses
from app.api.v1.transaction_rules.dependencies import (
    get_transaction_rule_directory_reader,
    get_transaction_rule_mutation_service,
)
from app.api.v1.transaction_rules.errors import transaction_rule_api_error
from app.api.v1.transaction_rules.parameters import (
    TransactionRuleDirectoryParameters,
    parse_transaction_rule_directory_parameters,
)
from app.api.v1.transaction_rules.schemas import (
    TransactionRuleCreateApiRequest,
    TransactionRuleCreateApiResponse,
    TransactionRuleDeleteApiRequest,
    TransactionRuleDeleteApiResponse,
    TransactionRuleDirectoryApiResponse,
    TransactionRuleEditApiResponse,
    TransactionRuleLifecycleApiRequest,
    TransactionRuleLifecycleApiResponse,
    TransactionRuleSeedDefaultsApiResponse,
    TransactionRuleSummaryApiResponse,
    TransactionRuleUpdateApiRequest,
)
from app.features.ledger.domain.money import affects_profit_for_operation_type
from app.features.transaction_rules.application.commands import (
    CreateTransactionRuleCommand,
    UpdateTransactionRuleCommand,
)
from app.features.transaction_rules.application.directory import (
    TransactionRuleDirectoryReader,
)
from app.features.transaction_rules.application.mutations import (
    TransactionRuleMutationService,
)
from app.features.transaction_rules.errors import TransactionRuleError
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
        target_rule_id=parameters.rule_id,
    )
    return TransactionRuleDirectoryApiResponse.model_validate(directory)


@router.post(
    "",
    response_model=TransactionRuleCreateApiResponse,
    status_code=status.HTTP_201_CREATED,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def create_transaction_rule(
    request: TransactionRuleCreateApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    mutations: Annotated[
        TransactionRuleMutationService,
        Depends(get_transaction_rule_mutation_service),
    ],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> TransactionRuleCreateApiResponse:
    affects_profit = (
        affects_profit_for_operation_type(request.operation_type)
        if request.operation_type is not None
        else True
    )
    command = CreateTransactionRuleCommand(
        name=request.name,
        pattern=request.pattern,
        match_type=request.match_type,
        category_id=request.category_id,
        property_id=request.property_id,
        target_operation_type=request.operation_type,
        direction=request.direction,
        amount_min=request.amount_min,
        amount_max=request.amount_max,
        affects_profit=affects_profit,
        application_mode=request.application_mode,
    )
    try:
        created = await mutations.create(
            context=context.workspace,
            command=command,
            idempotency_key=idempotency_key,
        )
    except TransactionRuleError as error:
        raise transaction_rule_api_error(error) from error
    return TransactionRuleCreateApiResponse.model_validate(created)


@router.post(
    "/seed-defaults",
    response_model=TransactionRuleSeedDefaultsApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def seed_default_transaction_rules(
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    mutations: Annotated[
        TransactionRuleMutationService,
        Depends(get_transaction_rule_mutation_service),
    ],
) -> TransactionRuleSeedDefaultsApiResponse:
    try:
        seeded = await mutations.seed_defaults(context=context.workspace)
    except TransactionRuleError as error:
        raise transaction_rule_api_error(error) from error
    return TransactionRuleSeedDefaultsApiResponse.model_validate(seeded)


@router.get(
    "/{rule_id}/edit",
    response_model=TransactionRuleEditApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    ),
)
async def get_transaction_rule_for_edit(
    rule_id: UUID,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    mutations: Annotated[
        TransactionRuleMutationService,
        Depends(get_transaction_rule_mutation_service),
    ],
) -> TransactionRuleEditApiResponse:
    try:
        editor = await mutations.get_for_edit(context=context.workspace, rule_id=rule_id)
    except TransactionRuleError as error:
        raise transaction_rule_api_error(error) from error
    return TransactionRuleEditApiResponse.model_validate(editor)


@router.put(
    "/{rule_id}",
    response_model=TransactionRuleSummaryApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_transaction_rule(
    rule_id: UUID,
    request: TransactionRuleUpdateApiRequest,
    context: Annotated[
        ApiRequestContext,
        Depends(require_api_financial_write_context),
    ],
    mutations: Annotated[
        TransactionRuleMutationService,
        Depends(get_transaction_rule_mutation_service),
    ],
) -> TransactionRuleSummaryApiResponse:
    command = UpdateTransactionRuleCommand(
        rule_id=rule_id,
        name=request.name,
        pattern=request.pattern,
        match_type=request.match_type,
        category_id=request.category_id,
        property_id=request.property_id,
        target_operation_type=request.operation_type,
        direction=request.direction,
        application_mode=request.application_mode,
        amount_min=request.amount_min,
        amount_max=request.amount_max,
        expected_updated_at=request.expected_updated_at,
    )
    try:
        updated = await mutations.update(context=context.workspace, command=command)
    except TransactionRuleError as error:
        raise transaction_rule_api_error(error) from error
    return TransactionRuleSummaryApiResponse.model_validate(updated)


async def _change_transaction_rule_lifecycle(
    *,
    rule_id: UUID,
    request: TransactionRuleLifecycleApiRequest,
    context: ApiRequestContext,
    mutations: TransactionRuleMutationService,
    is_active: bool,
) -> TransactionRuleLifecycleApiResponse:
    try:
        changed = await mutations.set_active(
            context=context.workspace,
            rule_id=rule_id,
            is_active=is_active,
            expected_active=request.expected_active,
            expected_updated_at=request.expected_updated_at,
        )
    except TransactionRuleError as error:
        raise transaction_rule_api_error(error) from error
    return TransactionRuleLifecycleApiResponse.model_validate(changed)


@router.post(
    "/{rule_id}/enable",
    response_model=TransactionRuleLifecycleApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def enable_transaction_rule(
    rule_id: UUID,
    request: TransactionRuleLifecycleApiRequest,
    context: Annotated[ApiRequestContext, Depends(require_api_financial_write_context)],
    mutations: Annotated[
        TransactionRuleMutationService,
        Depends(get_transaction_rule_mutation_service),
    ],
) -> TransactionRuleLifecycleApiResponse:
    return await _change_transaction_rule_lifecycle(
        rule_id=rule_id,
        request=request,
        context=context,
        mutations=mutations,
        is_active=True,
    )


@router.post(
    "/{rule_id}/disable",
    response_model=TransactionRuleLifecycleApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def disable_transaction_rule(
    rule_id: UUID,
    request: TransactionRuleLifecycleApiRequest,
    context: Annotated[ApiRequestContext, Depends(require_api_financial_write_context)],
    mutations: Annotated[
        TransactionRuleMutationService,
        Depends(get_transaction_rule_mutation_service),
    ],
) -> TransactionRuleLifecycleApiResponse:
    return await _change_transaction_rule_lifecycle(
        rule_id=rule_id,
        request=request,
        context=context,
        mutations=mutations,
        is_active=False,
    )


@router.delete(
    "/{rule_id}",
    response_model=TransactionRuleDeleteApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
    ),
)
async def delete_transaction_rule(
    rule_id: UUID,
    request: TransactionRuleDeleteApiRequest,
    context: Annotated[ApiRequestContext, Depends(require_api_financial_write_context)],
    mutations: Annotated[
        TransactionRuleMutationService,
        Depends(get_transaction_rule_mutation_service),
    ],
) -> TransactionRuleDeleteApiResponse:
    try:
        deleted = await mutations.delete(
            context=context.workspace,
            rule_id=rule_id,
            expected_active=request.expected_active,
            expected_updated_at=request.expected_updated_at,
        )
    except TransactionRuleError as error:
        raise transaction_rule_api_error(error) from error
    return TransactionRuleDeleteApiResponse(
        deleted_id=deleted.id,
        name=deleted.name,
    )
