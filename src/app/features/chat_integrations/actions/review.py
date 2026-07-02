from dataclasses import dataclass


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
class ChatReviewDocumentSelection:
    action_token: str
    document_index: int


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
class ChatReviewTransferExistingSelection:
    action_token: str
    transfer_index: int


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


class ChatReviewDocumentCallbackData:
    PREFIX = "rvd"

    @classmethod
    def build_document_selection(cls, *, action_token: str, document_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{document_index}"

    @classmethod
    def parse_document_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewDocumentSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            document_index = int(parts[2])
        except ValueError:
            return None
        return ChatReviewDocumentSelection(
            action_token=parts[1],
            document_index=document_index,
        )


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


class ChatReviewTransferExistingCallbackData:
    PREFIX = "rvo"

    @classmethod
    def build_existing_selection(cls, *, action_token: str, transfer_index: int) -> str:
        return f"{cls.PREFIX}:{action_token}:{transfer_index}"

    @classmethod
    def parse_existing_selection(
        cls,
        callback_data: str | None,
    ) -> ChatReviewTransferExistingSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 3 or parts[0] != cls.PREFIX:
            return None
        try:
            transfer_index = int(parts[2])
        except ValueError:
            return None
        return ChatReviewTransferExistingSelection(
            action_token=parts[1],
            transfer_index=transfer_index,
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
