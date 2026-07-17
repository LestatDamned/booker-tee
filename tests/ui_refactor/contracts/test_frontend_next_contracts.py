from pathlib import Path

from starlette.requests import Request

from app.web.templating import WEB_ROOT
from app.web.ui.responses import HtmxResponseMode, is_htmx_request


def test_htmx_response_modes_are_explicit() -> None:
    assert {mode.value for mode in HtmxResponseMode} == {
        "loadPanel",
        "replaceRow",
        "removeRow",
        "replaceList",
        "oobUpdate",
    }


def test_htmx_detection_requires_explicit_header() -> None:
    htmx_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/_next/foundation",
            "headers": [(b"hx-request", b"true")],
        }
    )
    normal_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/_next/foundation",
            "headers": [],
        }
    )

    assert is_htmx_request(htmx_request) is True
    assert is_htmx_request(normal_request) is False


def test_next_css_has_isolated_entry_point_and_semantic_contract() -> None:
    css_root = WEB_ROOT / "static" / "css"
    entry = (css_root / "app.css").read_text(encoding="utf-8")
    theme = (css_root / "themes" / "catppuccin-mocha.css").read_text(encoding="utf-8")
    row = (css_root / "components" / "workbench-row.css").read_text(encoding="utf-8")

    assert "settings/tokens.css" in entry
    assert "themes/catppuccin-mocha.css" in entry
    assert "components/workbench-row.css" in entry
    assert "src/app/static/css/app.css" not in entry
    assert "--color-money-income" in theme
    assert ".workbench-row__expansion" in row
    assert "@media (max-width: 920px)" in row


def test_shared_javascript_owns_mechanics_not_financial_semantics() -> None:
    javascript = (WEB_ROOT / "static" / "js" / "web-ui.js").read_text(encoding="utf-8")

    assert 'Alpine.data("disclosure"' in javascript
    assert "status === 409 || status === 422" in javascript
    assert 'const ROW_SELECTOR = ".workbench-row"' in javascript
    assert "restoreReplacementFocus" in javascript
    assert "operationType" not in javascript
    assert "amount >" not in javascript
    assert "amount <" not in javascript


def test_web_adapter_does_not_import_current_presentation_contracts() -> None:
    forbidden_imports = (
        "app.templating",
        "app.shared.ui",
        ".presentation.",
    )
    python_files = sorted(Path(WEB_ROOT).rglob("*.py"))

    assert python_files
    for path in python_files:
        source = path.read_text(encoding="utf-8")
        assert all(forbidden not in source for forbidden in forbidden_imports), path
