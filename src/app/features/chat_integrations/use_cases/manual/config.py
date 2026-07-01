from datetime import timedelta

from app.features.chat_integrations.models import ChatConversationFlow

CHAT_MANUAL_OPERATION_TTL = timedelta(minutes=30)
CHAT_MANUAL_ACCOUNT_MAX_CHOICES = 8
CHAT_MANUAL_CATEGORY_PAGE_SIZE = 7
CHAT_MANUAL_OPERATION_FLOWS = (
    ChatConversationFlow.RECORD_EXPENSE,
    ChatConversationFlow.RECORD_INCOME,
    ChatConversationFlow.RECORD_TRANSFER,
)
