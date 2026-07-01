from secrets import token_urlsafe


class ChatActionTokenBuilder:
    @staticmethod
    def build_token() -> str:
        return token_urlsafe(12)
