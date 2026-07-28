from importlib.util import find_spec
from typing import Any

from fastapi.testclient import TestClient as FastApiTestClient
from starlette.types import ASGIApp


class ApiTestClient(FastApiTestClient):
    __test__ = False

    def __init__(self, app: ASGIApp, **kwargs: Any) -> None:
        kwargs.setdefault(
            "backend_options",
            {"use_uvloop": find_spec("uvloop") is not None},
        )
        super().__init__(app, **kwargs)
