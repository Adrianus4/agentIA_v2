from pathlib import Path

from agents.profiles.loader import get_profile
from agents.scaffolder.service import SubprocessScaffolder
from contracts.models import ScaffoldRequest


def test_subprocess_scaffolder_uses_argv_and_collects_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")

        class Completed:
            returncode = 0
            stdout = "created"

        return Completed()

    monkeypatch.setattr("agents.scaffolder.service.subprocess.run", fake_run)
    profile = get_profile("quarkus", "3")
    request = ScaffoldRequest(
        group_id="com.example",
        artifact_id="billing",
        package_name="com.example.billing",
        java_version="17",
        extensions=["io.quarkus:quarkus-arc"],
        workspace_path=str(tmp_path),
    )

    result = SubprocessScaffolder().scaffold(request, profile)

    assert result.success
    assert captured["argv"][0] == "mvn"
    assert result.manifest[0].path == "pom.xml"


def test_subprocess_scaffolder_empty_manifest_fails_with_structured_error(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_run(argv, **kwargs):
        class Completed:
            returncode = 0
            stdout = "success but no files created"

        return Completed()

    monkeypatch.setattr("agents.scaffolder.service.subprocess.run", fake_run)
    profile = get_profile("quarkus", "3")
    request = ScaffoldRequest(
        group_id="com.example",
        artifact_id="billing",
        package_name="com.example.billing",
        java_version="17",
        extensions=["io.quarkus:quarkus-arc"],
        workspace_path=str(tmp_path),
    )

    result = SubprocessScaffolder().scaffold(request, profile)

    assert result.success is False
    assert result.error_code == "EMPTY_MANIFEST"
    assert result.manifest == []


def test_subprocess_scaffolder_nonzero_exit_code_fails(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_run(argv, **kwargs):
        class Completed:
            returncode = 1
            stdout = "build error"

        return Completed()

    monkeypatch.setattr("agents.scaffolder.service.subprocess.run", fake_run)
    profile = get_profile("quarkus", "3")
    request = ScaffoldRequest(
        group_id="com.example",
        artifact_id="billing",
        package_name="com.example.billing",
        java_version="17",
        extensions=["io.quarkus:quarkus-arc"],
        workspace_path=str(tmp_path),
    )

    result = SubprocessScaffolder().scaffold(request, profile)

    assert result.success is False
    assert result.exit_code == 1
    assert result.error_code == "SCAFFOLD_FAILED"
