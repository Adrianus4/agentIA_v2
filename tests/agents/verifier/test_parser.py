from pathlib import Path

from agents.verifier.parser import parse_maven_output
from contracts.models import DiagnosticIssue

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fixtures"


def test_parse_clean_output() -> None:
    clean_txt = (FIXTURES_DIR / "maven_clean.txt").read_text()
    issues = parse_maven_output(clean_txt)
    assert len(issues) == 0


def test_parse_single_compilation_error() -> None:
    error_txt = (FIXTURES_DIR / "maven_compile_error.txt").read_text()
    issues = parse_maven_output(error_txt)

    assert len(issues) == 1
    issue = issues[0]
    assert isinstance(issue, DiagnosticIssue)
    assert issue.file_path == "src/main/java/org/acme/GreetingResource.java"
    assert issue.line_number == 14
    assert issue.column_number == 25
    assert issue.error_type == "COMPILE_ERROR"
    assert "cannot find symbol" in issue.message
    assert "NonExistentService" in issue.message


def test_parse_multiple_compilation_errors() -> None:
    multi_txt = (FIXTURES_DIR / "maven_compile_multierror.txt").read_text()
    issues = parse_maven_output(multi_txt)

    assert len(issues) == 3

    assert issues[0].file_path == "src/main/java/org/acme/GreetingResource.java"
    assert issues[0].line_number == 14
    assert issues[0].column_number == 25
    assert "cannot find symbol" in issues[0].message

    assert issues[1].file_path == "src/main/java/org/acme/GreetingResource.java"
    assert issues[1].line_number == 22
    assert issues[1].column_number == 9
    assert "incompatible types" in issues[1].message

    assert issues[2].file_path == "src/main/java/org/acme/GreetingService.java"
    assert issues[2].line_number == 8
    assert issues[2].column_number == 1
    assert "';' expected" in issues[2].message


def test_parse_surefire_test_failure() -> None:
    clean_txt = (FIXTURES_DIR / "maven_clean.txt").read_text()
    surefire_dir = str(FIXTURES_DIR / "surefire-reports")

    issues = parse_maven_output(clean_txt, surefire_dir=surefire_dir)

    # Should find 1 failure (GreetingResourceTest) and 1 error (ServiceExceptionTest)
    # CleanTest has 0 failures/errors
    assert len(issues) == 2

    failure = next(i for i in issues if "GreetingResourceTest" in i.file_path)
    assert failure.file_path == "src/test/java/org/acme/GreetingResourceTest.java"
    assert failure.line_number == 24
    assert failure.error_type == "org.opentest4j.AssertionFailedError"
    assert "Hello World" in failure.message
    assert "Bye World" in failure.message

    error = next(i for i in issues if "ServiceExceptionTest" in i.file_path)
    assert error.file_path == "src/test/java/org/acme/ServiceExceptionTest.java"
    assert error.line_number == 18
    assert error.error_type == "java.lang.NullPointerException"
    assert "Cannot invoke" in error.message


def test_workspace_relative_path_normalization() -> None:
    custom_stdout = """
[ERROR] /home/developer/workspace/project/src/main/java/org/acme/Custom.java:[33,12] cannot find symbol
"""
    issues = parse_maven_output(
        custom_stdout,
        workspace_root="/home/developer/workspace/project"
    )
    assert len(issues) == 1
    assert issues[0].file_path == "src/main/java/org/acme/Custom.java"


def test_nonexistent_or_empty_surefire_dir(tmp_path: Path) -> None:
    clean_txt = (FIXTURES_DIR / "maven_clean.txt").read_text()
    issues = parse_maven_output(clean_txt, surefire_dir=str(tmp_path / "nonexistent"))
    assert len(issues) == 0


def test_malformed_xml_surefire_dir(tmp_path: Path) -> None:
    bad_xml = tmp_path / "TEST-bad.xml"
    bad_xml.write_text("<testsuite><unclosed>")
    clean_txt = (FIXTURES_DIR / "maven_clean.txt").read_text()
    issues = parse_maven_output(clean_txt, surefire_dir=str(tmp_path))
    assert len(issues) == 0


def test_parse_maven_output_deduplication() -> None:
    # Repeated identical lines in stdout
    duplicated_stdout = """
[ERROR] /workspace/src/main/java/org/acme/Order.java:[10,5] cannot find symbol
[ERROR]   symbol:   class Item
[ERROR] /workspace/src/main/java/org/acme/Order.java:[10,5] cannot find symbol
[ERROR]   symbol:   class Item
[ERROR] /workspace/src/main/java/org/acme/Order.java:[12,5] cannot find symbol
"""
    issues = parse_maven_output(duplicated_stdout)
    assert len(issues) == 2
    assert issues[0].file_path == "src/main/java/org/acme/Order.java"
    assert issues[0].line_number == 10
    assert issues[1].line_number == 12


def test_parse_windows_drive_path_compilation_error() -> None:
    # Maven on Windows prints absolute paths with a leading slash before the drive letter
    windows_stdout = """
[ERROR] COMPILATION ERROR : 
[ERROR] /C:/tmp/agentia-workspace/demo/src/main/java/com/example/UserResource.java:[34,42] cannot find symbol
[ERROR]   symbol:   variable Page
[ERROR]   location: class com.example.UserResource
"""
    issues = parse_maven_output(windows_stdout, workspace_root="C:/tmp/agentia-workspace/demo")
    assert len(issues) == 1
    assert issues[0].file_path == "src/main/java/com/example/UserResource.java"
    assert issues[0].line_number == 34
    assert issues[0].column_number == 42
    assert "variable Page" in issues[0].message
