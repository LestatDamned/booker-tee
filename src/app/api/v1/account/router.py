from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    AuthenticatedSessionContext,
    get_authenticated_session_context,
)
from app.api.errors import api_error_responses
from app.api.v1.account.dependencies import get_user_service
from app.api.v1.account.schemas import AccountApiResponse, UpdateAccountApiRequest
from app.features.users.service import UserService

router = APIRouter(prefix="/account", tags=["account"])


@router.get(
    "",
    response_model=AccountApiResponse,
    responses=api_error_responses(status.HTTP_401_UNAUTHORIZED),
)
async def read_account(
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
) -> AccountApiResponse:
    return AccountApiResponse.model_validate(context.user)


@router.patch(
    "",
    response_model=AccountApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    ),
)
async def update_account(
    request: UpdateAccountApiRequest,
    context: Annotated[
        AuthenticatedSessionContext,
        Depends(get_authenticated_session_context),
    ],
    users: Annotated[UserService, Depends(get_user_service)],
) -> AccountApiResponse:
    user = await users.update_name(user=context.user, name=request.name)
    return AccountApiResponse.model_validate(user)
