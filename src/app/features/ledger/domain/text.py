def clean_description(description: str | None) -> str | None:
    if description is None:
        return None
    cleaned = " ".join(description.split())
    return cleaned or None
