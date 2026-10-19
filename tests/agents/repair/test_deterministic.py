from agents.profiles.loader import get_profile
from agents.repair.deterministic import missing_import_patch
from agents.repair.service import ScopedRepairService
from app.orchestrator.patching import apply_patch
from contracts.models import DiagnosticIssue, FileContent, RepairRequest, TestBaseline

SOURCE = """package com.example.catalog.resource;

import java.util.List;

public class UserResource {
    List<User> list() { return repository.findAll().page(Page.of(0, 20)).list(); }
}
"""


def _request(message: str, dependencies=None) -> RepairRequest:
    return RepairRequest(
        framework="quarkus",
        framework_version="3.15",
        failing_file=FileContent(path="src/main/java/com/example/catalog/resource/UserResource.java", content=SOURCE),
        issues=[DiagnosticIssue(file_path="src/main/java/com/example/catalog/resource/UserResource.java", error_type="COMPILE_ERROR", message=message)],
        dependencies=dependencies or [],
        allowed_paths=["src/main/java/com/example/catalog/resource/UserResource.java"],
        test_baseline=TestBaseline(test_count=0, assertion_count=0, disabled_count=0),
    )


def test_missing_profile_type_is_imported_without_llm(tmp_path) -> None:
    profile = get_profile("quarkus", "3.15")
    request = _request("cannot find symbol\nsymbol:   variable Page\nlocation: class UserResource")

    def llm(_prompt: str) -> str:
        raise AssertionError("LLM must not be called for a deterministic import fix")

    result = ScopedRepairService(patch_generator=llm).repair(profile, request, "trace-det")
    assert result.outcome == "PATCHED"
    assert result.hypothesis.startswith("Deterministic import fix")

    target = tmp_path / request.failing_file.path
    target.parent.mkdir(parents=True)
    target.write_text(SOURCE, encoding="utf-8")
    apply_patch(str(tmp_path), result.patches[0], allowed_paths=[request.failing_file.path])
    assert "import io.quarkus.panache.common.Page;" in target.read_text(encoding="utf-8")


def test_project_class_is_resolved_from_dependencies() -> None:
    profile = get_profile("quarkus", "3.15")
    user = FileContent(path="src/main/java/com/example/catalog/User.java", content="package com.example.catalog;\npublic class User {}\n")
    patch = missing_import_patch(profile, _request("cannot find symbol\nsymbol:   class User", [user]))
    assert patch is not None and "import com.example.catalog.User;" in patch


def test_unknown_symbol_falls_through_to_llm() -> None:
    profile = get_profile("quarkus", "3.15")
    assert missing_import_patch(profile, _request("cannot find symbol\nsymbol:   class Mystery")) is None
    assert missing_import_patch(profile, _request("incompatible types: String cannot be converted to int")) is None
