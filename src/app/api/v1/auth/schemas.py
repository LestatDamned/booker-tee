from pydantic import Field

from app.api.schemas import ApiModel, ApiRequestModel


class AuthConfigApiResponse(ApiModel):
    allow_signups: bool
    password_min_length: int


class LoginApiRequest(ApiRequestModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)
    next_path: str | None = Field(default=None, max_length=2048)


class SignupApiRequest(LoginApiRequest):
    name: str | None = Field(default=None, max_length=255)


class AuthenticatedApiResponse(ApiModel):
    next_path: str
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class RefreshApiResponse(ApiModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class VerificationRequestedApiResponse(ApiModel):
    message: str
    retry_after_seconds: int


class EmailVerificationRequestApiRequest(ApiRequestModel):
    email: str = Field(max_length=320)


class EmailVerificationApiRequest(ApiRequestModel):
    token: str = Field(min_length=1, max_length=1024)
    next_path: str | None = Field(default=None, max_length=2048)


class PasswordResetRequestApiRequest(ApiRequestModel):
    email: str = Field(max_length=320)


class PasswordResetApiRequest(ApiRequestModel):
    token: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(max_length=1024)


class PasswordResetApiResponse(ApiModel):
    message: str
