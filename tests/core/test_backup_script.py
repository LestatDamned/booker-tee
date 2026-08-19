import hashlib
import json
import os
from pathlib import Path
from subprocess import run

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_backup_script_creates_verified_dump_without_originals(tmp_path: Path) -> None:
    env_file = tmp_path / "production.env"
    env_file.write_text("POSTGRES_DB=booker_tee\n", encoding="utf-8")
    env_file.chmod(0o600)
    command_log = tmp_path / "docker.log"
    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    docker = executable_dir / "docker"
    docker.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$DOCKER_LOG"
case "$1 $*" in
  "inspect "*) printf '%s\\n' 'registry.example/booker-tee@sha256:abc123' ;;
  *" ps --status running -q app") printf '%s\\n' 'app-container-id' ;;
  *"SELECT version_num FROM alembic_version"*) printf '%s\\n' '20260819_0032' ;;
  *"pg_dump "*)
    [ "${FAIL_DUMP:-0}" -eq 0 ] || exit 9
    printf '%s' 'fake-postgresql-custom-dump'
    ;;
esac
""",
        encoding="utf-8",
    )
    docker.chmod(0o700)
    backup_dir = tmp_path / "backup-set"

    result = run(
        [str(PROJECT_ROOT / "scripts/backup.sh"), str(backup_dir)],
        cwd=PROJECT_ROOT,
        env={
            "BOOKER_TEE_ENV_FILE": str(env_file),
            "DOCKER_LOG": str(command_log),
            "PATH": f"{executable_dir}:/usr/bin",
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert os.stat(backup_dir).st_mode & 0o777 == 0o700
    assert not (backup_dir / "INCOMPLETE").exists()
    manifest = json.loads((backup_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["application_image"] == "registry.example/booker-tee@sha256:abc123"
    assert manifest["alembic_revision"] == "20260819_0032"
    assert manifest["temporary_originals_included"] is False
    checksums = {
        filename: checksum
        for checksum, filename in (
            line.split("  ", 1)
            for line in (backup_dir / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        )
    }
    for filename in ("postgresql.dump", "manifest.json"):
        assert (
            hashlib.sha256((backup_dir / filename).read_bytes()).hexdigest() == checksums[filename]
        )
    assert not any(path.name.endswith((".pdf", ".xlsx")) for path in backup_dir.iterdir())
    commands = command_log.read_text(encoding="utf-8")
    assert "--project-name booker-tee-production" in commands
    assert "stop app" in commands
    assert "start app" in commands

    failed_backup_dir = tmp_path / "failed-backup-set"
    failed_env = {
        "BOOKER_TEE_ENV_FILE": str(env_file),
        "DOCKER_LOG": str(command_log),
        "FAIL_DUMP": "1",
        "PATH": f"{executable_dir}:/usr/bin",
    }
    failed_result = run(
        [str(PROJECT_ROOT / "scripts/backup.sh"), str(failed_backup_dir)],
        cwd=PROJECT_ROOT,
        env=failed_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert failed_result.returncode != 0
    assert (failed_backup_dir / "INCOMPLETE").exists()
    assert command_log.read_text(encoding="utf-8").count("start app") == 2

    unsafe_result = run(
        [str(PROJECT_ROOT / "scripts/backup.sh"), str(tmp_path / "unsafe")],
        cwd=PROJECT_ROOT,
        env={
            "BOOKER_TEE_BACKUP_PROJECT": "booker-tee",
            "BOOKER_TEE_ENV_FILE": str(env_file),
            "DOCKER_LOG": str(command_log),
            "PATH": f"{executable_dir}:/usr/bin",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert unsafe_result.returncode != 0
    assert "unsupported Compose project name" in unsafe_result.stderr
