from datetime import date

import pytest

from app.features.chat_integrations.actions.manual import (
    ChatManualAccountCallbackData,
    ChatManualAccountSelection,
    ChatManualCategoryCallbackData,
    ChatManualCategoryPageCallbackData,
    ChatManualCategoryPageSelection,
    ChatManualCategorySelection,
    ChatManualConfirmationCallbackData,
    ChatManualConfirmationSelection,
    ChatManualCorrectionCallbackData,
    ChatManualCorrectionSelection,
    ChatManualDateCallbackData,
    ChatManualDateSelection,
    ChatManualDescriptionCallbackData,
    ChatManualDescriptionSelection,
)
from app.features.chat_integrations.actions.review import (
    ChatReviewActionConfirmationCallbackData,
    ChatReviewCallbackData,
    ChatReviewCategoryCallbackData,
    ChatReviewCategoryPageCallbackData,
    ChatReviewCategoryPageSelection,
    ChatReviewCategorySelection,
    ChatReviewDocumentCallbackData,
    ChatReviewDocumentSelection,
    ChatReviewNavigationCallbackData,
    ChatReviewNavigationSelection,
    ChatReviewPropertyCallbackData,
    ChatReviewPropertySelection,
    ChatReviewReturnCallbackData,
    ChatReviewReturnSelection,
    ChatReviewRulePatternCallbackData,
    ChatReviewRulePatternSelection,
    ChatReviewRuleSuggestionCallbackData,
    ChatReviewRuleSuggestionSelection,
    ChatReviewTransferAccountSelection,
    ChatReviewTransferCallbackData,
    ChatReviewTransferConfirmationCallbackData,
    ChatReviewTransferExistingCallbackData,
    ChatReviewTransferExistingSelection,
    ChatReviewTransferPairCallbackData,
    ChatReviewTransferPairSelection,
)
from app.features.chat_integrations.actions.summary import (
    ChatSummaryCallbackData,
    ChatSummaryPeriodSelection,
)
from app.features.chat_integrations.actions.upload import (
    ChatUploadAccountSelection,
    ChatUploadCallbackData,
)
from app.features.chat_integrations.actions.workspace import (
    ChatWorkspaceCallbackData,
    ChatWorkspaceSelection,
)
from app.features.chat_integrations.providers.telegram import (
    TelegramCallbackDataPolicy,
    TelegramUpdateNormalizationError,
)


def test_telegram_callback_data_is_limited_to_64_bytes() -> None:
    assert TelegramCallbackDataPolicy.ensure_callback_data("expense:start") == "expense:start"

    with pytest.raises(TelegramUpdateNormalizationError):
        TelegramCallbackDataPolicy.ensure_callback_data("x" * 65)


def test_chat_review_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewCallbackData.build_ignore_action(action_token="shorttoken")

    assert len(callback_data) <= 64
    assert callback_data == "rev:shorttoken:ign"
    assert ChatReviewCallbackData.parse_action(callback_data) is not None
    assert ChatReviewCallbackData.build_duplicate_action(action_token="shorttoken") == (
        "rev:shorttoken:dup"
    )
    assert ChatReviewCallbackData.build_accept_suggestion_action(action_token="shorttoken") == (
        "rev:shorttoken:sug"
    )
    assert ChatReviewCallbackData.parse_action("review:next") is None
    confirmation_callback_data = ChatReviewActionConfirmationCallbackData.build_confirm_action(
        action_token="shorttoken",
    )
    assert len(confirmation_callback_data) <= 64
    assert confirmation_callback_data == "rva:shorttoken"
    assert (
        ChatReviewActionConfirmationCallbackData.parse_confirmation_selection(
            confirmation_callback_data
        )
        is not None
    )
    transfer_confirmation_callback_data = (
        ChatReviewTransferConfirmationCallbackData.build_confirm_action(
            action_token="shorttoken",
        )
    )
    assert len(transfer_confirmation_callback_data) <= 64
    assert transfer_confirmation_callback_data == "rvy:shorttoken"
    assert (
        ChatReviewTransferConfirmationCallbackData.parse_confirmation_selection(
            transfer_confirmation_callback_data
        )
        is not None
    )
    rule_save_callback_data = ChatReviewRuleSuggestionCallbackData.build_save_action(
        action_token="shorttoken",
    )
    assert len(rule_save_callback_data) <= 64
    assert rule_save_callback_data == "rvr:shorttoken:save"
    assert ChatReviewRuleSuggestionCallbackData.parse_action(rule_save_callback_data) == (
        ChatReviewRuleSuggestionSelection(action_token="shorttoken", action="save")
    )
    assert (
        ChatReviewRuleSuggestionCallbackData.build_enter_pattern_action(action_token="shorttoken")
        == "rvr:shorttoken:type"
    )
    rule_pattern_callback_data = ChatReviewRulePatternCallbackData.build_pattern_selection(
        action_token="shorttoken",
        pattern_index=2,
    )
    assert len(rule_pattern_callback_data) <= 64
    assert rule_pattern_callback_data == "rvq:shorttoken:2"
    assert ChatReviewRulePatternCallbackData.parse_pattern_selection(
        rule_pattern_callback_data
    ) == ChatReviewRulePatternSelection(action_token="shorttoken", pattern_index=2)
    workspace_callback_data = ChatWorkspaceCallbackData.build_workspace_selection(
        action_token="shorttoken",
        workspace_index=1,
    )
    assert len(workspace_callback_data) <= 64
    assert workspace_callback_data == "wsp:shorttoken:1"
    assert ChatWorkspaceCallbackData.parse_workspace_selection(workspace_callback_data) == (
        ChatWorkspaceSelection(action_token="shorttoken", workspace_index=1)
    )
    summary_callback_data = ChatSummaryCallbackData.build_period_selection(
        month_start=date(2026, 7, 1),
    )
    assert len(summary_callback_data) <= 64
    assert summary_callback_data == "sum:2026-07"
    assert ChatSummaryCallbackData.parse_period_selection(summary_callback_data) == (
        ChatSummaryPeriodSelection(month_start=date(2026, 7, 1))
    )
    category_summary_callback_data = ChatSummaryCallbackData.build_category_selection(
        month_start=date(2026, 7, 1),
    )
    assert len(category_summary_callback_data) <= 64
    assert category_summary_callback_data == "sumc:2026-07"
    assert ChatSummaryCallbackData.parse_category_selection(category_summary_callback_data) == (
        ChatSummaryPeriodSelection(month_start=date(2026, 7, 1))
    )


def test_chat_review_navigation_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewNavigationCallbackData.build_next_action(
        action_token="shorttoken",
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvn:shorttoken:next"
    assert ChatReviewNavigationCallbackData.parse_navigation_selection(callback_data) == (
        ChatReviewNavigationSelection(action_token="shorttoken", direction="next")
    )
    assert (
        ChatReviewNavigationCallbackData.build_previous_action(action_token="shorttoken")
        == "rvn:shorttoken:prev"
    )
    assert ChatReviewNavigationCallbackData.parse_navigation_selection("review:next") is None


def test_chat_review_return_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewReturnCallbackData.build_return_action(
        action_token="shorttoken",
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvb:shorttoken"
    assert ChatReviewReturnCallbackData.parse_return_selection(callback_data) == (
        ChatReviewReturnSelection(action_token="shorttoken")
    )
    assert ChatReviewReturnCallbackData.parse_return_selection("review:next") is None


def test_chat_review_document_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewDocumentCallbackData.build_document_selection(
        action_token="shorttoken",
        document_index=2,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvd:shorttoken:2"
    assert ChatReviewDocumentCallbackData.parse_document_selection(callback_data) == (
        ChatReviewDocumentSelection(action_token="shorttoken", document_index=2)
    )
    assert ChatReviewDocumentCallbackData.parse_document_selection("review:choose") is None


def test_chat_review_category_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewCategoryCallbackData.build_category_selection(
        action_token="shorttoken",
        category_index=2,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvc:shorttoken:2"
    assert ChatReviewCategoryCallbackData.parse_category_selection(callback_data) == (
        ChatReviewCategorySelection(action_token="shorttoken", category_index=2)
    )
    assert ChatReviewCategoryCallbackData.parse_category_selection("rev:shorttoken:conf") is None


def test_chat_review_category_page_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewCategoryPageCallbackData.build_page_action(
        action_token="shorttoken",
        page_index=2,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rcp:shorttoken:2"
    assert ChatReviewCategoryPageCallbackData.parse_page_selection(callback_data) == (
        ChatReviewCategoryPageSelection(action_token="shorttoken", page_index=2)
    )
    assert ChatReviewCategoryPageCallbackData.parse_page_selection("rvc:shorttoken:2") is None


def test_chat_review_property_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewPropertyCallbackData.build_property_selection(
        action_token="shorttoken",
        property_index=3,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvp:shorttoken:3"
    assert ChatReviewPropertyCallbackData.parse_property_selection(callback_data) == (
        ChatReviewPropertySelection(action_token="shorttoken", property_index=3)
    )
    assert ChatReviewPropertyCallbackData.parse_property_selection("rvc:shorttoken:3") is None


def test_chat_review_transfer_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewTransferCallbackData.build_account_selection(
        action_token="shorttoken",
        account_index=1,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvt:shorttoken:1"
    assert ChatReviewTransferCallbackData.parse_account_selection(callback_data) == (
        ChatReviewTransferAccountSelection(action_token="shorttoken", account_index=1)
    )
    assert ChatReviewTransferCallbackData.parse_account_selection("rvp:shorttoken:1") is None


def test_chat_review_transfer_pair_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewTransferPairCallbackData.build_pair_selection(
        action_token="shorttoken",
        pair_index=1,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvx:shorttoken:1"
    assert ChatReviewTransferPairCallbackData.parse_pair_selection(callback_data) == (
        ChatReviewTransferPairSelection(action_token="shorttoken", pair_index=1)
    )
    assert ChatReviewTransferPairCallbackData.parse_pair_selection("rvt:shorttoken:1") is None


def test_chat_review_transfer_existing_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatReviewTransferExistingCallbackData.build_existing_selection(
        action_token="shorttoken",
        transfer_index=1,
    )

    assert len(callback_data) <= 64
    assert callback_data == "rvo:shorttoken:1"
    assert ChatReviewTransferExistingCallbackData.parse_existing_selection(callback_data) == (
        ChatReviewTransferExistingSelection(action_token="shorttoken", transfer_index=1)
    )
    assert (
        ChatReviewTransferExistingCallbackData.parse_existing_selection("rvx:shorttoken:1") is None
    )


def test_chat_manual_callback_data_is_short_and_parseable() -> None:
    account_callback_data = ChatManualAccountCallbackData.build_account_selection(
        action_token="manualtoken",
        account_index=1,
    )
    assert len(account_callback_data) <= 64
    assert account_callback_data == "mna:manualtoken:1"
    assert ChatManualAccountCallbackData.parse_account_selection(account_callback_data) == (
        ChatManualAccountSelection(action_token="manualtoken", account_index=1)
    )
    assert ChatManualAccountCallbackData.parse_account_selection("mna:manualtoken:bad") is None

    category_callback_data = ChatManualCategoryCallbackData.build_category_selection(
        action_token="manualtoken",
        category_index=2,
    )
    assert len(category_callback_data) <= 64
    assert category_callback_data == "mnc:manualtoken:2"
    assert ChatManualCategoryCallbackData.parse_category_selection(category_callback_data) == (
        ChatManualCategorySelection(action_token="manualtoken", category_index=2)
    )

    category_page_callback_data = ChatManualCategoryPageCallbackData.build_page_action(
        action_token="manualtoken",
        page_index=1,
    )
    assert len(category_page_callback_data) <= 64
    assert category_page_callback_data == "mcp:manualtoken:1"
    assert ChatManualCategoryPageCallbackData.parse_page_selection(
        category_page_callback_data
    ) == ChatManualCategoryPageSelection(action_token="manualtoken", page_index=1)

    today_callback_data = ChatManualDateCallbackData.build_today_action(
        action_token="manualtoken",
    )
    assert len(today_callback_data) <= 64
    assert today_callback_data == "mnd:manualtoken:today"
    assert ChatManualDateCallbackData.parse_date_selection(today_callback_data) == (
        ChatManualDateSelection(action_token="manualtoken", date_action="today")
    )
    assert (
        ChatManualDateCallbackData.build_yesterday_action(action_token="manualtoken")
        == "mnd:manualtoken:yesterday"
    )
    assert (
        ChatManualDateCallbackData.build_custom_action(action_token="manualtoken")
        == "mnd:manualtoken:custom"
    )
    assert ChatManualDateCallbackData.parse_date_selection("mnd:manualtoken:unknown") is None

    description_callback_data = ChatManualDescriptionCallbackData.build_skip_action(
        action_token="manualtoken",
    )
    assert len(description_callback_data) <= 64
    assert description_callback_data == "mndsc:manualtoken:skip"
    assert ChatManualDescriptionCallbackData.parse_description_selection(
        description_callback_data
    ) == ChatManualDescriptionSelection(
        action_token="manualtoken",
        description_action="skip",
    )


def test_chat_manual_confirmation_and_correction_callback_data_is_parseable() -> None:
    correction_callback_data = ChatManualCorrectionCallbackData.build_description_action(
        action_token="manualtoken",
    )
    assert len(correction_callback_data) <= 64
    assert correction_callback_data == "mned:manualtoken:description"
    assert ChatManualCorrectionCallbackData.parse_correction_selection(
        correction_callback_data
    ) == ChatManualCorrectionSelection(
        action_token="manualtoken",
        correction_action="description",
    )
    assert (
        ChatManualCorrectionCallbackData.build_menu_action(action_token="manualtoken")
        == "mned:manualtoken:menu"
    )
    assert (
        ChatManualCorrectionCallbackData.build_amount_action(action_token="manualtoken")
        == "mned:manualtoken:amount"
    )
    assert (
        ChatManualCorrectionCallbackData.build_date_action(action_token="manualtoken")
        == "mned:manualtoken:date"
    )
    assert (
        ChatManualCorrectionCallbackData.build_category_action(action_token="manualtoken")
        == "mned:manualtoken:category"
    )
    assert (
        ChatManualCorrectionCallbackData.parse_correction_selection("mned:manualtoken:unknown")
        is None
    )

    confirmation_callback_data = ChatManualConfirmationCallbackData.build_confirm_action(
        action_token="manualtoken",
    )
    assert len(confirmation_callback_data) <= 64
    assert confirmation_callback_data == "mnf:manualtoken:ok"
    assert ChatManualConfirmationCallbackData.parse_confirm_action(
        confirmation_callback_data
    ) == ChatManualConfirmationSelection(action_token="manualtoken")
    assert ChatManualConfirmationCallbackData.parse_confirm_action("mnf:manualtoken:bad") is None


def test_chat_upload_callback_data_is_short_and_parseable() -> None:
    callback_data = ChatUploadCallbackData.build_account_selection(
        action_token="uploadtoken",
        account_index=3,
    )

    assert len(callback_data) <= 64
    assert callback_data == "upl:uploadtoken:3"
    assert ChatUploadCallbackData.parse_account_selection(callback_data) == (
        ChatUploadAccountSelection(action_token="uploadtoken", account_index=3)
    )
    assert ChatUploadCallbackData.parse_account_selection("upl:uploadtoken:bad") is None
