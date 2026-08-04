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
