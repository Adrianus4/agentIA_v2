from pathlib import Path

import pytest

from app.orchestrator.patching import PatchApplicationError, apply_patch


def _patch(old: str, new: str, path: str = "src/main.py") -> str:
    return (
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1 +1 @@\n"
        f"-{old}\n"
        f"+{new}\n"
    )


def test_applies_unified_diff_inside_workspace(tmp_path: Path) -> None:
    target = tmp_path / "src/main.py"
    target.parent.mkdir()
    target.write_text("old\n")

    assert apply_patch(str(tmp_path), _patch("old", "new")) is None
    assert target.read_text() == "new\n"


@pytest.mark.parametrize("path", ["../outside.txt", "nested/../../outside.txt"])
def test_rejects_relative_path_traversal_before_mutation(tmp_path: Path, path: str) -> None:
    sentinel = tmp_path.parent / "outside.txt"
    sentinel.write_text("unchanged\n")

    with pytest.raises(PatchApplicationError, match="(traversal|escapes)"):
        apply_patch(str(tmp_path), _patch("old", "changed", path))

    assert sentinel.read_text() == "unchanged\n"


def test_rejects_absolute_path_escape_before_mutation(tmp_path: Path) -> None:
    outside = tmp_path.parent / "absolute.txt"
    outside.write_text("unchanged\n")

    with pytest.raises(PatchApplicationError, match="escapes workspace"):
        apply_patch(str(tmp_path), _patch("old", "changed", str(outside)))

    assert outside.read_text() == "unchanged\n"


def test_rejects_mixed_safe_and_unsafe_patch_atomically(tmp_path: Path) -> None:
    safe = tmp_path / "safe.txt"
    safe.write_text("old\n")
    content = _patch("old", "changed", "safe.txt") + _patch(
        "old", "changed", "../unsafe.txt"
    )

    with pytest.raises(PatchApplicationError):
        apply_patch(str(tmp_path), content)

    assert safe.read_text() == "old\n"


def test_rejects_context_mismatch_without_partial_change(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("actual\n")

    with pytest.raises(PatchApplicationError):
        apply_patch(str(tmp_path), _patch("expected", "changed", "target.txt"))

    assert target.read_text() == "actual\n"


def test_applies_imperfect_llm_diff_with_empty_lines_and_wrong_hunk_counts(tmp_path: Path) -> None:
    target = tmp_path / "src/main/java/com/example/repository/ApiKeyRepository.java"
    target.parent.mkdir(parents=True)
    target.write_text(
        "package com.example.repository;\n"
        "\n"
        "import com.example.entity.ApiKey;\n"
        "import jakarta.enterprise.context.ApplicationScoped;\n"
        "import jakarta.transaction.Transactional;\n"
        "import io.quarkus.hibernate.orm.panache.PanacheRepository;\n"
        "import java.util.List;\n"
        "\n"
        "@ApplicationScoped\n"
        "public class ApiKeyRepository implements PanacheRepository<ApiKey> {\n"
        "\n"
        "    @Transactional\n"
        "    public List<ApiKey> findAll() {\n"
        "        return listAll();\n"
        "    }\n"
        "}\n"
    )

    imperfect_diff = (
        "--- src/main/java/com/example/repository/ApiKeyRepository.java\n"
        "+++ src/main/java/com/example/repository/ApiKeyRepository.java\n"
        "@@ -1,5 +1,5 @@\n"
        " package com.example.repository;\n"
        "\n"
        "-import com.example.entity.ApiKey;\n"
        " import jakarta.enterprise.context.ApplicationScoped;\n"
        " import jakarta.transaction.Transactional;\n"
        " import io.quarkus.hibernate.orm.panache.PanacheRepository;\n"
        "\n"
        "@@ -11,14 +11,14 @@ import java.util.List;\n"
        " @ApplicationScoped\n"
        " public class ApiKeyRepository implements PanacheRepository<ApiKey> {\n"
        "\n"
        "-    @Transactional\n"
        "     public List<ApiKey> findAll() {\n"
        "         return listAll();\n"
        "     }\n"
        " }\n"
    )

    apply_patch(str(tmp_path), imperfect_diff)
    result = target.read_text()
    assert "import com.example.entity.ApiKey;" not in result
    assert "@Transactional" not in result


def test_apply_patch_search_replace_block(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
    src_dir.mkdir(parents=True, exist_ok=True)
    target = src_dir / "ItemResource.java"
    target.write_text(
        "package com.example;\n\n"
        "public class ItemResource {\n"
        "    public Response getById(Long id) {\n"
        "        return repository.findByIdOptional(id).map(Response::ok);\n"
        "    }\n"
        "}\n"
    )

    block_patch = (
        "File: src/main/java/com/example/ItemResource.java\n"
        "<<<<<<< SEARCH\n"
        "        return repository.findByIdOptional(id).map(Response::ok);\n"
        "=======\n"
        "        return repository.findByIdOptional(id)\n"
        "            .map(entity -> Response.ok(entity).build())\n"
        "            .orElseGet(() -> Response.status(Response.Status.NOT_FOUND).build());\n"
        ">>>>>>> REPLACE\n"
    )

    apply_patch(str(tmp_path), block_patch)
    updated = target.read_text()
    assert "map(Response::ok)" not in updated
    assert "map(entity -> Response.ok(entity).build())" in updated
    assert "orElseGet(() -> Response.status(Response.Status.NOT_FOUND).build())" in updated


def test_apply_patch_whole_file_markdown_header(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "main" / "java" / "com" / "example" / "resource"
    src_dir.mkdir(parents=True, exist_ok=True)
    target = src_dir / "AutorizacionResource.java"
    target.write_text("package com.example.resource;\npublic class AutorizacionResource {}\n")

    llm_output = (
        "Here is the corrected file:\n\n"
        "### Modified `src/main/java/com/example/resource/AutorizacionResource.java`\n"
        "```java\n"
        "package com.example.resource;\n"
        "import jakarta.transaction.Transactional;\n\n"
        "public class AutorizacionResource {\n"
        "    @Transactional\n"
        "    public void delete() {}\n"
        "}\n"
        "```\n"
    )

    apply_patch(str(tmp_path), llm_output)
    updated = target.read_text()
    assert "import jakarta.transaction.Transactional;" in updated
    assert "@Transactional" in updated


def test_apply_patch_whole_file_inferred_from_package_and_class(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "main" / "java" / "com" / "example" / "resource"
    src_dir.mkdir(parents=True, exist_ok=True)
    target = src_dir / "CapturaResource.java"
    target.write_text("package com.example.resource;\npublic class CapturaResource {}\n")

    llm_output = (
        "I fixed the missing import in the class below:\n"
        "```java\n"
        "package com.example.resource;\n"
        "import jakarta.transaction.Transactional;\n\n"
        "public class CapturaResource {\n"
        "    @Transactional\n"
        "    public void update() {}\n"
        "}\n"
        "```\n"
    )

    apply_patch(str(tmp_path), llm_output)
    updated = target.read_text()
    assert "import jakarta.transaction.Transactional;" in updated
    assert "@Transactional" in updated


def test_apply_patch_sanitizes_missing_java_test_imports(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "test" / "java" / "com" / "example" / "repository"
    src_dir.mkdir(parents=True, exist_ok=True)
    target = src_dir / "TransaccionRepositoryTest.java"
    target.write_text("package com.example.repository;\npublic class TransaccionRepositoryTest {}\n")

    llm_output = (
        "File: src/test/java/com/example/repository/TransaccionRepositoryTest.java\n"
        "```java\n"
        "package com.example.repository;\n\n"
        "public class TransaccionRepositoryTest {\n"
        "    @InjectMock\n"
        "    TransaccionRepository repository;\n\n"
        "    public void test() {\n"
        "        List<String> list = new ArrayList<>();\n"
        "        BigDecimal amount = new BigDecimal(10);\n"
        "        assertThat(list.size(), is(0));\n"
        "    }\n"
        "}\n"
        "```\n"
    )

    apply_patch(str(tmp_path), llm_output)
    updated = target.read_text()
    assert "import io.quarkus.test.junit.mockito.InjectMock;" in updated
    assert "import java.util.*;" in updated
    assert "import java.math.BigDecimal;" in updated
    assert "import static org.hamcrest.CoreMatchers.*;" in updated


def test_apply_patch_sanitizes_timestamp_and_hamcrest_wildcard(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "test" / "java" / "com" / "example" / "resource"
    src_dir.mkdir(parents=True, exist_ok=True)
    target = src_dir / "ItemResourceTest.java"
    target.write_text("package com.example.resource;\npublic class ItemResourceTest {}\n")

    llm_output = (
        "File: src/test/java/com/example/resource/ItemResourceTest.java\n"
        "```java\n"
        "package com.example.resource;\n"
        "import static org.hamcrest.CoreMatchers.notNullValue;\n\n"
        "public class ItemResourceTest {\n"
        "    public void test() {\n"
        "        Timestamp ts = new Timestamp(System.currentTimeMillis());\n"
        "        equalTo(\"abc\");\n"
        "    }\n"
        "}\n"
        "```\n"
    )

    apply_patch(str(tmp_path), llm_output)
    updated = target.read_text()
    assert "import java.sql.Timestamp;" in updated
    assert "import static org.hamcrest.CoreMatchers.*;" in updated


def test_apply_patch_sanitizes_panache_findbyid_optional(tmp_path: Path) -> None:
    src_dir = tmp_path / "src" / "test" / "java" / "com" / "example" / "repository"
    src_dir.mkdir(parents=True, exist_ok=True)
    target = src_dir / "ItemRepositoryTest.java"
    target.write_text("package com.example.repository;\npublic class ItemRepositoryTest {}\n")

    llm_output = (
        "File: src/test/java/com/example/repository/ItemRepositoryTest.java\n"
        "```java\n"
        "package com.example.repository;\n\n"
        "public class ItemRepositoryTest {\n"
        "    ItemRepository repository;\n"
        "    public void test() {\n"
        "        Item item = repository.findById(1L).get();\n"
        "        Item item2 = repository.findById(2L).orElse(null);\n"
        "        Item item3 = repository.findById(3L).orElseThrow();\n"
        "    }\n"
        "}\n"
        "```\n"
    )

    apply_patch(str(tmp_path), llm_output)
    updated = target.read_text()
    assert "repository.findByIdOptional(1L).get()" in updated
    assert "repository.findByIdOptional(2L).orElse(null)" in updated
    assert "repository.findByIdOptional(3L).orElseThrow()" in updated




