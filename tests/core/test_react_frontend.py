from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.react_frontend import install_react_frontend


def test_react_frontend_serves_index_for_direct_navigation(tmp_path: Path) -> None:
    build_root = tmp_path / "client"
    build_root.mkdir()
    (build_root / "index.html").write_text("<h1>React shell</h1>", encoding="utf-8")
    assets_root = build_root / "assets"
    assets_root.mkdir()
    (assets_root / "app.js").write_text("console.log('shell')", encoding="utf-8")
    app = FastAPI()
    install_react_frontend(app, build_root=build_root)

    with TestClient(app) as client:
        root_response = client.get("/app")
        nested_response = client.get("/app/ledger/manual")
        asset_response = client.get("/assets/app.js")

    assert root_response.status_code == 200
    assert nested_response.status_code == 200
    assert "React shell" in nested_response.text
    assert asset_response.status_code == 200


def test_react_frontend_reports_missing_local_build(tmp_path: Path) -> None:
    app = FastAPI()
    install_react_frontend(app, build_root=tmp_path / "missing")

    with TestClient(app) as client:
        response = client.get("/app")

    assert response.status_code == 503
