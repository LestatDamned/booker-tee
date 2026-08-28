from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_statement_upload_has_ip_rate_and_connection_limits() -> None:
    nginx = (PROJECT_ROOT / "docker/nginx/default.conf.template").read_text()
    upload = nginx.split("location = /api/v1/imports/documents {", 1)[1].split("}", 1)[0]

    assert "POST $binary_remote_addr" in nginx
    assert "rate=6r/m" in nginx
    assert "limit_req zone=statement_upload burst=3 nodelay" in upload
    assert "limit_conn statement_upload_connections 2" in upload
    assert "client_max_body_size 25m" in upload
    assert "limit_req_status 429" in nginx
    assert "limit_conn_status 429" in nginx
