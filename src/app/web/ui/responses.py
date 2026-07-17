from enum import StrEnum

from fastapi import Request


class HtmxResponseMode(StrEnum):
    LOAD_PANEL = "loadPanel"
    REPLACE_ROW = "replaceRow"
    REMOVE_ROW = "removeRow"
    REPLACE_LIST = "replaceList"
    OOB_UPDATE = "oobUpdate"


def is_htmx_request(request: Request) -> bool:
    return request.headers.get("HX-Request") == "true"
