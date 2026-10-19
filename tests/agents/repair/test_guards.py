"""
Unit tests for DM-3 Patch Guards (G1 and G7).
"""



from agents.repair.guards import evaluate_guards, extract_touched_files
from contracts.models import (
    DiagnosticIssue,
    FileContent,
    GuardReport,
    RepairRequest,
    TestBaseline,
)


def create_request(
    allowed_paths: list[str] | None = None,
    failing_path: str = "src/main/java/org/acme/GreetingResource.java",
) -> RepairRequest:
    if allowed_paths is None:
        allowed_paths = ["src/main/java/org/acme/GreetingResource.java"]
    return RepairRequest(
        framework="framework-x",
        framework_version="1.0",
        failing_file=FileContent(
            path=failing_path,
            content="public class GreetingResource { public String hello() { return null; } }",
        ),
        issues=[
            DiagnosticIssue(
                file_path=failing_path,
                line_number=1,
                column_number=1,
                error_type="COMPILE_ERROR",
                message="cannot find symbol",
            )
        ],
        allowed_paths=allowed_paths,
        attempt_budget=3,
        test_baseline=TestBaseline(
            test_count=2,
            assertion_count=4,
            disabled_count=0,
        ),
    )


def test_valid_patch_allowed_file():
    """Patch touching only allowed file must pass all guards."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "--- a/src/main/java/org/acme/GreetingResource.java\n"
        "+++ b/src/main/java/org/acme/GreetingResource.java\n"
        "@@ -1,3 +1,3 @@\n"
        "-    public String hello() { return null; }\n"
        "+    public String hello() { return \"hello\"; }\n"
    )
    report = evaluate_guards(request, patch)
    assert isinstance(report, GuardReport)
    assert report.passed is True
    assert report.failed_guards == []


def test_guard_g1_fails_unallowed_file():
    """Patch touching file outside allowed_paths must fail Guard G1."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "--- a/src/main/java/org/acme/OtherService.java\n"
        "+++ b/src/main/java/org/acme/OtherService.java\n"
        "@@ -1,3 +1,3 @@\n"
        "-    void foo() {}\n"
        "+    void bar() {}\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G1" in report.failed_guards
    assert "G7" not in report.failed_guards


def test_guard_g7_fails_pom_xml_not_allowed():
    """Patch modifying pom.xml when pom.xml is not allowed must fail both G1 and G7."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "--- a/pom.xml\n"
        "+++ b/pom.xml\n"
        "@@ -10,3 +10,8 @@\n"
        "+    <dependency>\n"
        "+        <groupId>evil</groupId>\n"
        "+        <artifactId>backdoor</artifactId>\n"
        "+    </dependency>\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G1" in report.failed_guards
    assert "G7" in report.failed_guards


def test_guard_g7_passes_when_pom_xml_is_in_allowed_paths():
    """When pom.xml is explicitly listed in allowed_paths, G7 must not fail."""
    request = create_request(
        allowed_paths=["src/main/java/org/acme/GreetingResource.java", "pom.xml"]
    )
    patch = (
        "--- a/pom.xml\n"
        "+++ b/pom.xml\n"
        "@@ -10,3 +10,4 @@\n"
        "+    <!-- legitimate update -->\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is True
    assert report.failed_guards == []


def test_adversarial_sneaking_pom_in_multifile_diff():
    """Adversarial diff touches an allowed file, but sneaks a pom.xml modification hunk."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "--- a/src/main/java/org/acme/GreetingResource.java\n"
        "+++ b/src/main/java/org/acme/GreetingResource.java\n"
        "@@ -1,2 +1,2 @@\n"
        "-    void test() {}\n"
        "+    void test() { ok(); }\n"
        "--- a/pom.xml\n"
        "+++ b/pom.xml\n"
        "@@ -5,1 +5,6 @@\n"
        "+    <dependency><groupId>unauthorized</groupId></dependency>\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G1" in report.failed_guards
    assert "G7" in report.failed_guards


def test_adversarial_path_traversal_pom():
    """Adversarial path traversal like 'src/main/../../pom.xml' must resolve and trigger G7."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "--- a/src/main/../../pom.xml\n"
        "+++ b/src/main/../../pom.xml\n"
        "@@ -1,1 +1,2 @@\n"
        "+<malicious/>\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G1" in report.failed_guards
    assert "G7" in report.failed_guards


def test_adversarial_subproject_pom_xml():
    """Modifying subproject pom.xml when unallowed must trigger G1 and G7."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "--- a/submodule/pom.xml\n"
        "+++ b/submodule/pom.xml\n"
        "@@ -1,1 +1,2 @@\n"
        "+<malicious/>\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G1" in report.failed_guards
    assert "G7" in report.failed_guards


def test_adversarial_git_rename_to_pom():
    """Git rename header pointing to pom.xml must be detected."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "diff --git a/dummy.xml b/pom.xml\n"
        "similarity index 100%\n"
        "rename from dummy.xml\n"
        "rename to pom.xml\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G1" in report.failed_guards
    assert "G7" in report.failed_guards


def test_adversarial_git_diff_header_only():
    """Git diff header without ---/+++ must still detect touched pom.xml."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "diff --git a/pom.xml b/pom.xml\n"
        "index abc1234..def5678 100644\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G1" in report.failed_guards
    assert "G7" in report.failed_guards


def test_adversarial_dev_null_creation_and_deletion():
    """Creation of pom.xml from /dev/null must be detected as pom.xml modification."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "--- /dev/null\n"
        "+++ b/pom.xml\n"
        "@@ -0,0 +1,5 @@\n"
        "+<project></project>\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G1" in report.failed_guards
    assert "G7" in report.failed_guards

    # Deletion of pom.xml to /dev/null
    delete_patch = (
        "--- a/pom.xml\n"
        "+++ /dev/null\n"
        "@@ -1,5 +0,0 @@\n"
        "-<project></project>\n"
    )
    delete_report = evaluate_guards(request, delete_patch)
    assert delete_report.passed is False
    assert "G1" in delete_report.failed_guards
    assert "G7" in delete_report.failed_guards


def test_patch_with_timestamps_and_tabs():
    """Diff lines containing tab-delimited timestamps must be cleanly parsed."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "--- a/src/main/java/org/acme/GreetingResource.java\t2026-10-11 12:00:00.000000000 +0000\n"
        "+++ b/src/main/java/org/acme/GreetingResource.java\t2026-10-11 12:01:00.000000000 +0000\n"
        "@@ -1,3 +1,3 @@\n"
        "-    void foo() {}\n"
        "+    void foo() { ok(); }\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is True
    assert report.failed_guards == []


def test_path_normalization_variations():
    """Relative path variants (./, leading slash, backslashes) must normalize cleanly."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "--- ./src/main/java/org/acme/GreetingResource.java\n"
        "+++ ./src/main/java/org/acme/GreetingResource.java\n"
        "@@ -1,1 +1,1 @@\n"
        "-a\n"
        "+b\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is True
    assert report.failed_guards == []


def test_extract_touched_files_helper():
    """extract_touched_files helper should accurately return all normalized touched files."""
    patch = (
        "diff --git a/file1.java b/file1.java\n"
        "--- a/file1.java\n"
        "+++ b/file1.java\n"
        "@@ -1 +1 @@\n"
        "-x\n"
        "+y\n"
        "--- /dev/null\n"
        "+++ b/file2.java\n"
        "@@ -0,0 +1 @@\n"
        "+new\n"
    )
    touched = extract_touched_files(patch)
    assert set(touched) == {"file1.java", "file2.java"}


def test_adversarial_binary_files_diff():
    """Binary files diff header mentioning pom.xml must be detected."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = "Binary files a/pom.xml and b/pom.xml differ\n"
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G1" in report.failed_guards
    assert "G7" in report.failed_guards


def test_index_header_diff():
    """Diff with Index: header must be detected."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    patch = (
        "Index: pom.xml\n"
        "===================================================================\n"
        "--- pom.xml\n"
        "+++ pom.xml\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G1" in report.failed_guards
    assert "G7" in report.failed_guards


def test_empty_patch_evaluates_cleanly():
    """Empty or non-modifying patch does not violate guards."""
    request = create_request(allowed_paths=["src/main/java/org/acme/GreetingResource.java"])
    report = evaluate_guards(request, "")
    assert report.passed is True
    assert report.failed_guards == []
    assert extract_touched_files("") == []


def test_extract_touched_files_modified_markdown_header():
    """LLM markdown header with ### Modified `path` should be recognized."""
    patch = "### Modified `src/main/java/org/acme/GreetingResource.java`\n```java\ncode\n```"
    touched = extract_touched_files(patch, ["src/main/java/org/acme/GreetingResource.java"])
    assert touched == ["src/main/java/org/acme/GreetingResource.java"]


def test_extract_touched_files_java_class_fallback():
    """LLM output without file header but containing Java class matching allowed paths."""
    patch = "```java\npackage org.acme;\npublic class GreetingResource {}\n```"
    touched = extract_touched_files(patch, ["src/main/java/org/acme/GreetingResource.java"])
    assert touched == ["src/main/java/org/acme/GreetingResource.java"]


def test_extract_touched_files_short_filename_matches_allowed_path():
    """LLM output with short filename header (e.g. File: GreetingResource.java) matches full allowed path."""
    patch = "File: GreetingResource.java\n```java\npackage org.acme;\npublic class GreetingResource {}\n```"
    allowed = ["src/main/java/org/acme/GreetingResource.java"]
    touched = extract_touched_files(patch, allowed)
    assert touched == ["src/main/java/org/acme/GreetingResource.java"]
    request = create_request(allowed_paths=allowed)
    report = evaluate_guards(request, patch)
    assert report.passed is True
    assert report.failed_guards == []


def test_guard_g3_fails_when_assertion_deleted():
    """Patch deleting test assertions in a test file must trigger Guard G3."""
    test_path = "src/test/java/org/acme/GreetingResourceTest.java"
    request = create_request(allowed_paths=[test_path], failing_path=test_path)
    patch = (
        f"--- a/{test_path}\n"
        f"+++ b/{test_path}\n"
        "@@ -10,3 +10,2 @@\n"
        "-    assertEquals(200, response.getStatus());\n"
        "+    // Removed test check\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is False
    assert "G3" in report.failed_guards


def test_guard_g3_passes_without_assertion_deletion():
    """Patch modifying test file without deleting assertions passes Guard G3."""
    test_path = "src/test/java/org/acme/GreetingResourceTest.java"
    request = create_request(allowed_paths=[test_path], failing_path=test_path)
    patch = (
        f"--- a/{test_path}\n"
        f"+++ b/{test_path}\n"
        "@@ -10,2 +10,2 @@\n"
        "-    int timeout = 5000;\n"
        "+    int timeout = 10000;\n"
    )
    report = evaluate_guards(request, patch)
    assert report.passed is True
    assert "G3" not in report.failed_guards





def test_g1_ignores_dotted_java_identifiers_in_prose():
    # LLM prose quoting a fully qualified class name must not count as a touched file
    patch = (
        "`Page` cannot be found because `io.quarkus.panache.common.Page` is not imported.\n"
        "File: src/main/java/org/acme/GreetingResource.java\n"
        "<<<<<<< SEARCH\n"
        "public class GreetingResource {\n"
        "=======\n"
        "public class GreetingResource { // fixed\n"
        ">>>>>>> REPLACE\n"
    )
    touched = extract_touched_files(patch, ["src/main/java/org/acme/GreetingResource.java"])
    assert touched == ["src/main/java/org/acme/GreetingResource.java"]
    report = evaluate_guards(create_request(), patch)
    assert report.passed, report.failed_guards


def test_g1_still_flags_backticked_unallowed_file():
    patch = "Also update `src/main/java/org/acme/Other.java`\n"
    report = evaluate_guards(create_request(), patch)
    assert "G1" in report.failed_guards


def test_class_fallback_ignores_prose_mentions_of_class():
    patch = (
        "The `UserResource` class has been modified to use the Page class from the library.\n"
        "public class GreetingResource { }\n"
    )
    assert extract_touched_files(patch, ["src/main/java/org/acme/GreetingResource.java"]) == [
        "src/main/java/org/acme/GreetingResource.java"
    ]
