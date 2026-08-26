from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_production_cleanup_service_is_hourly_hardened_and_observable() -> None:
    compose = (PROJECT_ROOT / "compose.production.yaml").read_text()
    cleanup = compose.split("\n  upload-cleanup:\n", 1)[1].split("\n  nginx:\n", 1)[0]

    assert "source_cleanup" in cleanup
    assert "sleep 3600" in cleanup
    assert "exit 1" in cleanup
    assert "restart: unless-stopped" in cleanup
    assert "booker_tee_uploads:/app/var/uploads" in cleanup
    assert "- database" in cleanup
    assert "read_only: true" in cleanup
    assert "cap_drop:\n      - ALL" in cleanup
    assert "no-new-privileges:true" in cleanup
    assert "cpus:" in cleanup
    assert "mem_limit:" in cleanup
    assert "pids_limit:" in cleanup
