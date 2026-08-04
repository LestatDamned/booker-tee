class UserError(ValueError):
    pass


class InvalidEmailError(UserError):
    pass


class InvalidPasswordError(UserError):
    pass


class EmailAlreadyRegisteredError(UserError):
    pass


class InvalidCredentialsError(UserError):
    pass


class SignupsClosedError(UserError):
    pass


class InvalidEmailVerificationTokenError(UserError):
    pass


class InvalidPasswordResetTokenError(UserError):
    pass


class CurrentPasswordIncorrectError(UserError):
    pass


class CurrentSessionCannotBeRevokedError(UserError):
    pass


class UserSessionNotFoundError(UserError):
    pass


class AuthRateLimitedError(UserError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Слишком много запросов. Повторите позже.")
        self.retry_after_seconds = retry_after_seconds
