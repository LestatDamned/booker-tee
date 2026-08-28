import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RELEASE = "a" * 40


def test_first_production_deploy_uses_verified_images_and_migrates_before_start(
    tmp_path: Path,
) -> None:
    commands = tmp_path / "commands"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _executable(
        bin_dir / "git",
        f'''#!/bin/sh
if [ "$1 $2" = "rev-parse HEAD" ]; then printf '%s\\n' "{RELEASE}"; fi
exit 0
''',
    )
    _executable(
        bin_dir / "docker",
        f'''#!/bin/sh
printf '%s\\n' "$*" >>"{commands}"
exit 0
''',
    )
    _executable(bin_dir / "flock", "#!/bin/sh\nexit 0\n")
    env_file = tmp_path / "production.env"
    env_file.write_text("BOOKER_TEE_ENVIRONMENT=production\n")
    env_file.chmod(0o600)
    environment = os.environ | {
        "BOOKER_TEE_BACKUP_ROOT": str(tmp_path / "backups"),
        "BOOKER_TEE_DEPLOY_LOCK_FILE": str(tmp_path / "deploy.lock"),
        "BOOKER_TEE_ENV_FILE": str(env_file),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }

    result = subprocess.run(
        [
            str(PROJECT_ROOT / "scripts/deploy-production.sh"),
            RELEASE,
            f"ghcr.io/example/booker-tee:{RELEASE}",
            f"ghcr.io/example/booker-tee-nginx:{RELEASE}",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = commands.read_text()
    assert "pull app parser upload-cleanup nginx" in calls
    assert calls.index("run --rm app alembic upgrade head") < calls.index("up -d --wait\n")
    assert "run --rm --no-deps app python -m app.features.chat_integrations.webhook" in calls
    assert not (tmp_path / "backups").exists()


def _executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o700)
