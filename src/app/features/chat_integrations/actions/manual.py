from dataclasses import dataclass


@dataclass(frozen=True)
class ChatManualAccountSelection:
    action_token: str
    account_index: int


@dataclass(frozen=True)
class ChatManualCategorySelection:
    action_token: str
    category_index: int


@dataclass(frozen=True)
class ChatManualDateSelection:
    action_token: str
    date_action: str


@dataclass(frozen=True)
class ChatManualDescriptionSelection:
    action_token: str
    description_action: str


@dataclass(frozen=True)
class ChatManualCorrectionSelection:
    action_token: str
    correction_action: str


@dataclass(frozen=True)
class ChatManualConfirmationSelection:
    action_token: str


class ChatManualAccountCallbackData:
    PREFIX = "mna"

    @classmethod
    def build_account_selection(cls, *, action_token: str, account_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{account_index}"

    @classmethod
    def parse_account_selection(
        cls,
        callback_data: str | None,
    ) -> ChatManualAccountSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            account_index = int(parts[2])
        except ValueError:
            return None
        return ChatManualAccountSelection(
            action_token=parts[1],
            account_index=account_index,
        )


class ChatManualCategoryCallbackData:
    PREFIX = "mnc"

    @classmethod
    def build_category_selection(cls, *, action_token: str, category_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{category_index}"

    @classmethod
    def parse_category_selection(
        cls,
        callback_data: str | None,
    ) -> ChatManualCategorySelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            category_index = int(parts[2])
        except ValueError:
            return None
        return ChatManualCategorySelection(
            action_token=parts[1],
            category_index=category_index,
        )


class ChatManualDateCallbackData:
    PREFIX = "mnd"
    TODAY_ACTION = "today"
    YESTERDAY_ACTION = "yesterday"
    CUSTOM_ACTION = "custom"

    @classmethod
    def build_today_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, date_action=cls.TODAY_ACTION)

    @classmethod
    def build_yesterday_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, date_action=cls.YESTERDAY_ACTION)

    @classmethod
    def build_custom_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, date_action=cls.CUSTOM_ACTION)

    @classmethod
    def parse_date_selection(
        cls,
        callback_data: str | None,
    ) -> ChatManualDateSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        if parts[2] not in {
            cls.TODAY_ACTION,
            cls.YESTERDAY_ACTION,
            cls.CUSTOM_ACTION,
        }:
            return None
        return ChatManualDateSelection(action_token=parts[1], date_action=parts[2])

    @classmethod
    def _build_action(cls, *, action_token: str, date_action: str) -> str:
        return f"{cls.PREFIX}:{action_token}:{date_action}"


class ChatManualDescriptionCallbackData:
    PREFIX = "mndsc"
    SKIP_ACTION = "skip"

    @classmethod
    def build_skip_action(cls, *, action_token: str) -> str:
        return f"{cls.PREFIX}:{action_token}:{cls.SKIP_ACTION}"

    @classmethod
    def parse_description_selection(
        cls,
        callback_data: str | None,
    ) -> ChatManualDescriptionSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX or parts[2] != cls.SKIP_ACTION:
            return None
        return ChatManualDescriptionSelection(
            action_token=parts[1],
            description_action=parts[2],
        )


class ChatManualCorrectionCallbackData:
    PREFIX = "mned"
    MENU_ACTION = "menu"
    AMOUNT_ACTION = "amount"
    DATE_ACTION = "date"
    CATEGORY_ACTION = "category"
    DESCRIPTION_ACTION = "description"

    @classmethod
    def build_menu_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, correction_action=cls.MENU_ACTION)

    @classmethod
    def build_amount_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, correction_action=cls.AMOUNT_ACTION)

    @classmethod
    def build_date_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, correction_action=cls.DATE_ACTION)

    @classmethod
    def build_category_action(cls, *, action_token: str) -> str:
        return cls._build_action(
            action_token=action_token,
            correction_action=cls.CATEGORY_ACTION,
        )

    @classmethod
    def build_description_action(cls, *, action_token: str) -> str:
        return cls._build_action(
            action_token=action_token,
            correction_action=cls.DESCRIPTION_ACTION,
        )

    @classmethod
    def parse_correction_selection(
        cls,
        callback_data: str | None,
    ) -> ChatManualCorrectionSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        if parts[2] not in {
            cls.MENU_ACTION,
            cls.AMOUNT_ACTION,
            cls.DATE_ACTION,
            cls.CATEGORY_ACTION,
            cls.DESCRIPTION_ACTION,
        }:
            return None
        return ChatManualCorrectionSelection(
            action_token=parts[1],
            correction_action=parts[2],
        )

    @classmethod
    def _build_action(cls, *, action_token: str, correction_action: str) -> str:
        return f"{cls.PREFIX}:{action_token}:{correction_action}"


class ChatManualConfirmationCallbackData:
    PREFIX = "mnf"
    CONFIRM_ACTION = "ok"

    @classmethod
    def build_confirm_action(cls, *, action_token: str) -> str:
        return f"{cls.PREFIX}:{action_token}:{cls.CONFIRM_ACTION}"

    @classmethod
    def parse_confirm_action(
        cls,
        callback_data: str | None,
    ) -> ChatManualConfirmationSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX or parts[2] != cls.CONFIRM_ACTION:
            return None
        return ChatManualConfirmationSelection(action_token=parts[1])
