def append_review_message(existing: str | None, message: str) -> str:
    if not existing:
        return message
    if message in existing:
        return existing
    return f"{existing}; {message}"
