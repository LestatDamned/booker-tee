from pydantic import Field

from app.api.schemas import ApiModel, ApiRequestModel


class AuthConfigApiResponse(ApiModel):
    allow_signups: bool


class LoginApiRequest(ApiRequestModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)
    next_path: str | None = Field(default=None, max_length=2048)


class SignupApiRequest(LoginApiRequest):
    name: str | None = Field(default=None, max_length=255)


class AuthenticatedApiResponse(ApiModel):
    next_path: str
