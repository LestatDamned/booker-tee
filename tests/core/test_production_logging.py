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
