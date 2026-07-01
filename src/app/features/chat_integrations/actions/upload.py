from dataclasses import dataclass


@dataclass(frozen=True)
class ChatUploadAccountSelection:
    action_token: str
    account_index: int


class ChatUploadCallbackData:
    PREFIX = "upl"

    @classmethod
    def build_account_selection(cls, *, action_token: str, account_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{account_index}"

    @classmethod
    def parse_account_selection(
        cls, callback_data: str | None
    ) -> ChatUploadAccountSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            account_index = int(parts[2])
        except ValueError:
            return None
        return ChatUploadAccountSelection(action_token=parts[1], account_index=account_index)
