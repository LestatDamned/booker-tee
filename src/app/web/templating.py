from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from markupsafe import Markup

WEB_ROOT = Path(__file__).resolve().parent
WEB_TEMPLATES_ROOT = WEB_ROOT / "templates"
WEB_STATIC_ROOT = WEB_ROOT / "static"


def create_web_templates() -> Jinja2Templates:
    templates = Jinja2Templates(
        directory=WEB_TEMPLATES_ROOT,
        context_processors=[web_context],
    )
    cast(dict[str, Any], templates.env.globals)["csrf_input"] = csrf_input
    return templates


def web_context(request: Request) -> dict[str, object]:
    workspace_context = getattr(request.state, "workspace_context", None)
    return {
        "current_user": workspace_context.user if workspace_context else None,
        "current_workspace": workspace_context.workspace if workspace_context else None,
        "csrf_token": getattr(request.state, "csrf_token", None),
        "web_asset_version": static_tree_version(WEB_STATIC_ROOT),
    }


def static_tree_version(root: Path) -> str:
    digest = sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        stat = path.stat()
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(str(stat.st_mtime_ns).encode())
        digest.update(str(stat.st_size).encode())
    return digest.hexdigest()[:12]


@pass_context
def csrf_input(context: Any) -> Markup:
    token = context.get("csrf_token")
    if not token:
        return Markup("")
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')
