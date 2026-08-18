from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import api_error_responses
from app.api.v1.session.mapper import SessionApiResponseMapper
from app.api.v1.session.responses import SessionApiResponse

router = APIRouter(tags=["session"])


@router.get(
    "/session",
    response_model=SessionApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def read_session(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
) -> SessionApiResponse:
    return SessionApiResponseMapper.from_context(context)


@router.get(
    "/auth/me",
    response_model=SessionApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def read_current_user(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
) -> SessionApiResponse:
    return SessionApiResponseMapper.from_context(context)
