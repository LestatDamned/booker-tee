import base64
import hashlib
from pathlib import Path

from fastapi import FastAPI

from api_client import ApiTestClient as TestClient
from app.react_frontend import CONTENT_SECURITY_POLICY, install_react_frontend


def test_react_frontend_serves_index_for_direct_navigation(tmp_path: Path) -> None:
    build_root = tmp_path / "client"
    build_root.mkdir()
    inline_script = "window.__booker = { ready: true };"
    (build_root / "index.html").write_text(
        f"<h1>React shell</h1><script>{inline_script}</script>"
        '<script src="/assets/app.js"></script>',
        encoding="utf-8",
    )
    assets_root = build_root / "assets"
    assets_root.mkdir()
    (assets_root / "app.js").write_text("console.log('shell')", encoding="utf-8")
    app = FastAPI()
    install_react_frontend(app, build_root=build_root)

    with TestClient(app) as client:
        root_response = client.get("/app")
        nested_response = client.get("/app/operations")
        asset_response = client.get("/assets/app.js")

    assert root_response.status_code == 200
    assert nested_response.status_code == 200
    assert "React shell" in nested_response.text
    assert nested_response.headers["Cache-Control"] == "no-store"
    assert nested_response.headers["Referrer-Policy"] == "no-referrer"
    expected_hash = base64.b64encode(hashlib.sha256(inline_script.encode()).digest()).decode()
    unexpected_hash = base64.b64encode(hashlib.sha256(b"alert('injected')").digest()).decode()
    policy = nested_response.headers[CONTENT_SECURITY_POLICY]
    assert f"script-src 'self' 'sha256-{expected_hash}'" in policy
    assert unexpected_hash not in policy
    assert "default-src 'none'" in policy
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "Content-Security-Policy-Report-Only" not in nested_response.headers
    assert asset_response.headers.get(CONTENT_SECURITY_POLICY) is None
    assert asset_response.status_code == 200


def test_react_frontend_reports_missing_local_build(tmp_path: Path) -> None:
    app = FastAPI()
    install_react_frontend(app, build_root=tmp_path / "missing")

    with TestClient(app) as client:
        response = client.get("/app")

    assert response.status_code == 503
