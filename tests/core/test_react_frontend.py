from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
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


def test_historical_manual_ledger_url_redirects_with_query(tmp_path: Path) -> None:
    app = FastAPI()
    install_react_frontend(app, build_root=tmp_path / "missing")

    with TestClient(app) as client:
        response = client.get(
            "/ledger/manual?type=expense&page=2",
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == "/app/ledger/manual?type=expense&page=2"


def test_historical_import_review_url_redirects_with_query(tmp_path: Path) -> None:
    app = FastAPI()
    install_react_frontend(app, build_root=tmp_path / "missing")

    with TestClient(app) as client:
        response = client.get(
            "/imports/documents/document-id/review?source=chat",
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == ("/app/imports/documents/document-id/review?source=chat")


def test_historical_imports_url_redirects_with_query(tmp_path: Path) -> None:
    app = FastAPI()
    install_react_frontend(app, build_root=tmp_path / "missing")

    with TestClient(app) as client:
        response = client.get(
            "/imports?source=dashboard",
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == "/app/imports?source=dashboard"


def test_historical_import_document_url_redirects_with_query() -> None:
    document_id = "5e4c43a1-7e08-4afe-a442-5d1d72e08ca8"
    app = create_app()

    with TestClient(app) as client:
        response = client.get(
            f"/imports/documents/{document_id}?source=dashboard",
            follow_redirects=False,
        )

    assert response.status_code == 307
    assert response.headers["location"] == (
        f"/app/imports/documents/{document_id}?source=dashboard"
    )


def test_historical_import_upload_only_redirects_get_with_query() -> None:
    app = create_app()

    with TestClient(app) as client:
        get_response = client.get(
            "/imports/upload?source=dashboard",
            follow_redirects=False,
        )
        post_response = client.post(
            "/imports/upload",
            follow_redirects=False,
        )

    assert get_response.status_code == 307
    assert get_response.headers["location"] == ("/app/imports/upload?source=dashboard")
    assert post_response.status_code == 405
