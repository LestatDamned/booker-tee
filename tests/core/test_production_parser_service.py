from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.settings import Settings

PROJECT_ROOT = Path(__file__).parents[2]


def test_production_parser_service_is_isolated_and_bounded() -> None:
    compose = (PROJECT_ROOT / "compose.production.yaml").read_text()
    parser = compose.split("\n  parser:\n", 1)[1].split("\n  upload-cleanup:\n", 1)[0]
    development_compose = (PROJECT_ROOT / "compose.yaml").read_text()
    development_parser = development_compose.split("\n  parser:\n", 1)[1].split(
        "\n  frontend:\n", 1
    )[0]
    release_gate = (PROJECT_ROOT / "scripts/release-gate.sh").read_text()

    assert "network_mode: none" in parser
    assert "env_file:" not in parser
    assert "booker_tee_uploads" not in parser
    assert 'user: "10002:10001"' in parser
    assert "read_only: true" in parser
    assert "cap_drop:\n      - ALL" in parser
    assert "no-new-privileges:true" in parser
    assert "cpus:" in parser
    assert "mem_limit:" in parser
    assert "pids_limit:" in parser
    assert "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777" in parser
    assert "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777" in development_parser
    assert "compose exec -T parser python -c" in release_gate
    assert "tempfile.NamedTemporaryFile()" in release_gate
    assert "st_mode & 0o777 == 0o600" in release_gate
    assert "assert not os.path.exists(path)" in release_gate
    assert "parser-ipc/parser.sock" in parser
    assert "sidecar.client" in parser


def test_parser_cpu_limit_cannot_exceed_wall_timeout() -> None:
    with pytest.raises(ValidationError, match="CPU limit"):
        Settings(
            statement_parser_cpu_seconds=61,
            statement_parser_wall_timeout_seconds=60,
        )
