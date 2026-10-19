import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
QA_SCRIPT = REPO_ROOT / "scripts" / "qa.py"


def create_minimal_repo(base_dir: Path, test_files: dict[str, str] | None = None) -> Path:
    """Create a minimal controlled repository fixture for testing qa_agent."""
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "pyproject.toml").write_text(
        '[project]\nname = "fixture-repo"\nversion = "0.1.0"\nrequires-python = ">=3.11"\n'
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["."]\n',
        encoding="utf-8",
    )
    tests_dir = base_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")

    if test_files is None:
        test_files = {
            "test_basic.py": (
                "def test_ok_one():\n"
                "    assert 1 + 1 == 2\n\n"
                "def test_ok_two():\n"
                "    assert 'agentia'.upper() == 'AGENTIA'\n"
            )
        }
    for rel_path, content in test_files.items():
        target = tests_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    sentinel = base_dir / "sentinel.txt"
    sentinel.write_text("SENTINEL_UNTOUCHED", encoding="utf-8")
    return base_dir


def run_qa_cli(
    args: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    use_script: bool = False,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    """Run qa_agent via module or scripts/qa.py in a real subprocess."""
    if use_script:
        cmd = [sys.executable, str(QA_SCRIPT), *args]
    else:
        cmd = [sys.executable, "-m", "qa_agent", *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd or REPO_ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )


@pytest.fixture
def controlled_repo(tmp_path: Path) -> Path:
    return create_minimal_repo(tmp_path / "controlled_repo")
