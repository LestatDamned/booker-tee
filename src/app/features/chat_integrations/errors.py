class ChatIntegrationError(ValueError):
    pass


class ChatIdentityBindingError(ChatIntegrationError):
    pass


class ChatWorkspaceResolutionError(ChatIntegrationError):
    pass


class ChatWorkspaceSwitchError(ChatIntegrationError):
    pass


class ChatDocumentUploadError(ChatIntegrationError):
    pass


class ChatReviewActionError(ChatIntegrationError):
    pass


class ChatManualOperationError(ChatIntegrationError):
    pass
