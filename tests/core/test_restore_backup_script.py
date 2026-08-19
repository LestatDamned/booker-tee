import hashlib
import json
from pathlib import Path
from subprocess import run

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def prepare_restore_test(tmp_path: Path) -> tuple[Path, Path, Path]:
    env_file = tmp_path / "production.env"
    env_file.write_text("POSTGRES_DB=booker_tee\n", encoding="utf-8")
    env_file.chmod(0o600)
    backup_dir = tmp_path / "backup-set"
    backup_dir.mkdir(mode=0o700)
    (backup_dir / "postgresql.dump").write_bytes(b"fake-postgresql-custom-dump")
    (backup_dir / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "alembic_revision": "20260819_0032",
                "temporary_originals_included": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    checksums = "".join(
        f"{hashlib.sha256((backup_dir / filename).read_bytes()).hexdigest()}  {filename}\n"
        for filename in ("postgresql.dump", "manifest.json")
    )
    (backup_dir / "SHA256SUMS").write_text(checksums, encoding="utf-8")

    executable_dir = tmp_path / "bin"
    executable_dir.mkdir()
    docker = executable_dir / "docker"
    docker.write_text(
        """#!/bin/sh
printf '%s\\n' "$*" >> "$DOCKER_LOG"
case "$1 $2" in
  "volume inspect") [ "${VOLUME_EXISTS:-0}" -eq 0 ] || exit 0; exit 1 ;;
  "volume create") exit 0 ;;
esac
case "$*" in
  *"pg_catalog.pg_tables"*) printf '%s\\n' '0' ;;
  *"pg_restore "*) cat >/dev/null ;;
  *"SELECT version_num FROM alembic_version"*) printf '%s\\n' '20260819_0032' ;;
esac
""",
        encoding="utf-8",
    )
    docker.chmod(0o700)
    return env_file, backup_dir, executable_dir


def run_restore(
    tmp_path: Path,
    *,
    project: str,
    volume_exists: bool = False,
):
    env_file, backup_dir, executable_dir = prepare_restore_test(tmp_path)
    return run(
        [str(PROJECT_ROOT / "scripts/restore-backup.sh"), str(backup_dir), project],
        cwd=PROJECT_ROOT,
        env={
            "BOOKER_TEE_ENV_FILE": str(env_file),
            "DOCKER_LOG": str(tmp_path / "docker.log"),
            "PATH": f"{executable_dir}:/usr/bin",
            "VOLUME_EXISTS": "1" if volume_exists else "0",
        },
        capture_output=True,
        text=True,
        check=False,
    )


def test_restore_backup_uses_clean_isolated_project(tmp_path: Path) -> None:
    result = run_restore(tmp_path, project="booker-tee-restore-test")

    assert result.returncode == 0, result.stderr
    commands = (tmp_path / "docker.log").read_text(encoding="utf-8")
    assert "--project-name booker-tee-restore-test" in commands
    assert "up -d --wait postgres" in commands
    assert "pg_restore" in commands
    assert "booker-tee-restore-test_booker_tee_uploads" in commands


def test_restore_backup_rejects_production_project(tmp_path: Path) -> None:
    result = run_restore(tmp_path, project="booker-tee-production")

    assert result.returncode != 0
    assert "must start with booker-tee-restore-" in result.stderr
    assert not (tmp_path / "docker.log").exists()


def test_restore_backup_rejects_existing_volume(tmp_path: Path) -> None:
    result = run_restore(
        tmp_path,
        project="booker-tee-restore-existing",
        volume_exists=True,
    )

    assert result.returncode != 0
    assert "isolated volume already exists" in result.stderr
    assert " compose " not in (tmp_path / "docker.log").read_text(encoding="utf-8")
