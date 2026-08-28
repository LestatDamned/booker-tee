from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_production_access_logs_exclude_request_secrets() -> None:
    nginx = (PROJECT_ROOT / "docker/nginx/default.conf.template").read_text()
    safe_format = nginx.split("log_format safe ", 1)[1].split(";", 1)[0]
    compose = (PROJECT_ROOT / "compose.production.yaml").read_text()

    assert "$uri" in safe_format
    assert "$request_uri" not in safe_format
    assert "$args" not in safe_format
    assert "$http_referer" not in safe_format
    assert "$request_body" not in safe_format
    assert "$http_authorization" not in safe_format
    assert nginx.count("access_log /var/log/nginx/access.log safe;") == 2
    assert "--no-access-log" in compose


def test_production_app_container_is_hardened() -> None:
    compose = (PROJECT_ROOT / "compose.production.yaml").read_text()
    app_service = compose.split("  app:\n", 1)[1].split("  nginx:\n", 1)[0]

    assert "read_only: true" in app_service
    assert "/tmp:rw,noexec,nosuid,nodev,size=128m,mode=1777" in app_service
    assert "cap_drop:\n      - ALL" in app_service
    assert "security_opt:\n      - no-new-privileges:true" in app_service
    assert "booker_tee_uploads:/app/var/uploads" in app_service


def test_production_assets_cannot_be_transformed_by_proxies() -> None:
    nginx = (PROJECT_ROOT / "docker/nginx/default.conf.template").read_text()
    assets = nginx.split("location /assets/ {", 1)[1].split("}", 1)[0]

    assert 'Cache-Control "public, max-age=31536000, immutable, no-transform"' in assets
