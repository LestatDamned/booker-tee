from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.features.chat_integrations.schemas import ChatProviderCode


@dataclass(frozen=True)
class BindChatIdentityCommand:
    workspace_id: UUID
    user_id: UUID
    provider: ChatProviderCode
    external_user_id: str
    display_name: str | None = None


@dataclass(frozen=True)
class ChatWorkspaceSelection:
    action_token: str
    workspace_index: int


class ChatWorkspaceCallbackData:
    PREFIX = "wsp"

    @classmethod
    def build_workspace_selection(cls, *, action_token: str, workspace_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{workspace_index}"

    @classmethod
    def parse_workspace_selection(
        cls,
        callback_data: str | None,
    ) -> ChatWorkspaceSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            workspace_index = int(parts[2])
        except ValueError:
            return None
        return ChatWorkspaceSelection(
            action_token=parts[1],
            workspace_index=workspace_index,
        )


@dataclass(frozen=True)
class ChatSummaryPeriodSelection:
    month_start: date


class ChatSummaryCallbackData:
    PERIOD_PREFIX = "sum"
    CATEGORIES_PREFIX = "sumc"

    @classmethod
    def build_period_selection(cls, *, month_start: date) -> str:
        return f"{cls.PERIOD_PREFIX}:{cls._format_month(month_start)}"

    @classmethod
    def build_category_selection(cls, *, month_start: date) -> str:
        return f"{cls.CATEGORIES_PREFIX}:{cls._format_month(month_start)}"

    @classmethod
    def parse_period_selection(
        cls,
        callback_data: str | None,
    ) -> ChatSummaryPeriodSelection | None:
        return cls._parse_selection(callback_data, prefix=cls.PERIOD_PREFIX)

    @classmethod
    def parse_category_selection(
        cls,
        callback_data: str | None,
    ) -> ChatSummaryPeriodSelection | None:
        return cls._parse_selection(callback_data, prefix=cls.CATEGORIES_PREFIX)

    @classmethod
    def _parse_selection(
        cls,
        callback_data: str | None,
        *,
        prefix: str,
    ) -> ChatSummaryPeriodSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 2 or parts[0] != prefix:
            return None

        month_parts = parts[1].split("-")
        if len(month_parts) != 2:
            return None
        try:
            return ChatSummaryPeriodSelection(
                month_start=date(int(month_parts[0]), int(month_parts[1]), 1)
            )
        except ValueError:
            return None

    @staticmethod
    def _format_month(month_start: date) -> str:
        return month_start.strftime("%Y-%m")


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


@dataclass(frozen=True)
class ChatReviewActionSelection:
    action_token: str
    action: str


@dataclass(frozen=True)
class ChatReviewActionConfirmationSelection:
    action_token: str


@dataclass(frozen=True)
class ChatReviewNavigationSelection:
    action_token: str
    direction: str


@dataclass(frozen=True)
class ChatReviewReturnSelection:
    action_token: str


@dataclass(frozen=True)
class ChatReviewCategorySelection:
    action_token: str
    category_index: int


@dataclass(frozen=True)
class ChatReviewCategoryPageSelection:
    action_token: str
    page_index: int


@dataclass(frozen=True)
class ChatReviewPropertySelection:
    action_token: str
    property_index: int


@dataclass(frozen=True)
class ChatReviewTransferAccountSelection:
    action_token: str
    account_index: int


@dataclass(frozen=True)
class ChatReviewTransferPairSelection:
    action_token: str
    pair_index: int


@dataclass(frozen=True)
class ChatReviewTransferConfirmationSelection:
    action_token: str


@dataclass(frozen=True)
class ChatReviewRuleSuggestionSelection:
    action_token: str
    action: str


@dataclass(frozen=True)
class ChatReviewRulePatternSelection:
    action_token: str
    pattern_index: int


class ChatReviewCallbackData:
    PREFIX = "rev"
    CONFIRM_ACTION = "conf"
    DUPLICATE_ACTION = "dup"
    IGNORE_ACTION = "ign"
    MARK_UNIQUE_ACTION = "uniq"
    TRANSFER_ACTION = "trn"
    ACCEPT_SUGGESTION_ACTION = "sug"

    @classmethod
    def build_confirm_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, action=cls.CONFIRM_ACTION)

    @classmethod
    def build_accept_suggestion_action(cls, *, action_token: str) -> str:
        return cls._build_action(
            action_token=action_token,
            action=cls.ACCEPT_SUGGESTION_ACTION,
        )

    @classmethod
    def build_duplicate_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, action=cls.DUPLICATE_ACTION)

    @classmethod
    def build_ignore_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, action=cls.IGNORE_ACTION)

    @classmethod
    def build_mark_unique_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, action=cls.MARK_UNIQUE_ACTION)

    @classmethod
    def build_transfer_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, action=cls.TRANSFER_ACTION)

    @classmethod
    def parse_action(cls, callback_data: str | None) -> ChatReviewActionSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        if parts[2] not in {
            cls.CONFIRM_ACTION,
            cls.DUPLICATE_ACTION,
            cls.IGNORE_ACTION,
            cls.MARK_UNIQUE_ACTION,
            cls.TRANSFER_ACTION,
            cls.ACCEPT_SUGGESTION_ACTION,
        }:
            return None
        return ChatReviewActionSelection(action_token=parts[1], action=parts[2])

    @classmethod
    def _build_action(cls, *, action_token: str, action: str) -> str:
        return f"{cls.PREFIX}:{action_token}:{action}"


class ChatReviewActionConfirmationCallbackData:
    PREFIX = "rva"

    @classmethod
    def build_confirm_action(cls, *, action_token: str) -> str:
        return f"{cls.PREFIX}:{action_token}"

    @classmethod
    def parse_confirmation_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewActionConfirmationSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 2 or parts[0] != cls.PREFIX:
            return None
        return ChatReviewActionConfirmationSelection(action_token=parts[1])


class ChatReviewNavigationCallbackData:
    PREFIX = "rvn"
    NEXT_DIRECTION = "next"
    PREVIOUS_DIRECTION = "prev"

    @classmethod
    def build_next_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, direction=cls.NEXT_DIRECTION)

    @classmethod
    def build_previous_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, direction=cls.PREVIOUS_DIRECTION)

    @classmethod
    def parse_navigation_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewNavigationSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        if parts[2] not in {cls.NEXT_DIRECTION, cls.PREVIOUS_DIRECTION}:
            return None
        return ChatReviewNavigationSelection(action_token=parts[1], direction=parts[2])

    @classmethod
    def _build_action(cls, *, action_token: str, direction: str) -> str:
        return f"{cls.PREFIX}:{action_token}:{direction}"


class ChatReviewReturnCallbackData:
    PREFIX = "rvb"

    @classmethod
    def build_return_action(cls, *, action_token: str) -> str:
        return f"{cls.PREFIX}:{action_token}"

    @classmethod
    def parse_return_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewReturnSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 2 or parts[0] != cls.PREFIX:
            return None
        return ChatReviewReturnSelection(action_token=parts[1])


class ChatReviewCategoryCallbackData:
    PREFIX = "rvc"

    @classmethod
    def build_category_selection(cls, *, action_token: str, category_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{category_index}"

    @classmethod
    def parse_category_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewCategorySelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            category_index = int(parts[2])
        except ValueError:
            return None
        return ChatReviewCategorySelection(
            action_token=parts[1],
            category_index=category_index,
        )


class ChatReviewCategoryPageCallbackData:
    PREFIX = "rcp"

    @classmethod
    def build_page_action(cls, *, action_token: str, page_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{page_index}"

    @classmethod
    def parse_page_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewCategoryPageSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            page_index = int(parts[2])
        except ValueError:
            return None
        return ChatReviewCategoryPageSelection(
            action_token=parts[1],
            page_index=page_index,
        )


class ChatReviewPropertyCallbackData:
    PREFIX = "rvp"

    @classmethod
    def build_property_selection(cls, *, action_token: str, property_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{property_index}"

    @classmethod
    def parse_property_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewPropertySelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            property_index = int(parts[2])
        except ValueError:
            return None
        return ChatReviewPropertySelection(
            action_token=parts[1],
            property_index=property_index,
        )


class ChatReviewTransferCallbackData:
    PREFIX = "rvt"

    @classmethod
    def build_account_selection(cls, *, action_token: str, account_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{account_index}"

    @classmethod
    def parse_account_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewTransferAccountSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            account_index = int(parts[2])
        except ValueError:
            return None
        return ChatReviewTransferAccountSelection(
            action_token=parts[1],
            account_index=account_index,
        )


class ChatReviewTransferPairCallbackData:
    PREFIX = "rvx"

    @classmethod
    def build_pair_selection(cls, *, action_token: str, pair_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{pair_index}"

    @classmethod
    def parse_pair_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewTransferPairSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            pair_index = int(parts[2])
        except ValueError:
            return None
        return ChatReviewTransferPairSelection(
            action_token=parts[1],
            pair_index=pair_index,
        )


class ChatReviewTransferConfirmationCallbackData:
    PREFIX = "rvy"

    @classmethod
    def build_confirm_action(cls, *, action_token: str) -> str:
        return f"{cls.PREFIX}:{action_token}"

    @classmethod
    def parse_confirmation_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewTransferConfirmationSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 2 or parts[0] != cls.PREFIX:
            return None
        return ChatReviewTransferConfirmationSelection(action_token=parts[1])


class ChatReviewRuleSuggestionCallbackData:
    PREFIX = "rvr"
    SAVE_ACTION = "save"
    SKIP_ACTION = "skip"
    CHOOSE_PATTERN_ACTION = "pick"
    ENTER_PATTERN_ACTION = "type"

    @classmethod
    def build_save_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, action=cls.SAVE_ACTION)

    @classmethod
    def build_skip_action(cls, *, action_token: str) -> str:
        return cls._build_action(action_token=action_token, action=cls.SKIP_ACTION)

    @classmethod
    def build_choose_pattern_action(cls, *, action_token: str) -> str:
        return cls._build_action(
            action_token=action_token,
            action=cls.CHOOSE_PATTERN_ACTION,
        )

    @classmethod
    def build_enter_pattern_action(cls, *, action_token: str) -> str:
        return cls._build_action(
            action_token=action_token,
            action=cls.ENTER_PATTERN_ACTION,
        )

    @classmethod
    def parse_action(
        cls,
        callback_data: str | None,
    ) -> ChatReviewRuleSuggestionSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        if parts[2] not in {
            cls.SAVE_ACTION,
            cls.SKIP_ACTION,
            cls.CHOOSE_PATTERN_ACTION,
            cls.ENTER_PATTERN_ACTION,
        }:
            return None
        return ChatReviewRuleSuggestionSelection(action_token=parts[1], action=parts[2])

    @classmethod
    def _build_action(cls, *, action_token: str, action: str) -> str:
        return f"{cls.PREFIX}:{action_token}:{action}"


class ChatReviewRulePatternCallbackData:
    PREFIX = "rvq"

    @classmethod
    def build_pattern_selection(cls, *, action_token: str, pattern_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{pattern_index}"

    @classmethod
    def parse_pattern_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewRulePatternSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            pattern_index = int(parts[2])
        except ValueError:
            return None
        return ChatReviewRulePatternSelection(
            action_token=parts[1],
            pattern_index=pattern_index,
        )


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
