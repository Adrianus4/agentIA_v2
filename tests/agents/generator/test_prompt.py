import inspect

from contracts.models import FrameworkProfile


def _create_sample_profile(
    concepts: dict | None = None,
    test_style: dict | None = None,
    forbidden_imports: list[str] | None = None,
) -> FrameworkProfile:
    return FrameworkProfile(
        id="test-profile",
        framework="custom-fw",
        framework_version="1.0",
        profile_revision=1,
        java_version="17",
        build_tool="maven",
        enabled=True,
        instruction_set_revision="v1",
        concepts=concepts
        or {
            "orm_entity": {
                "annotations": ["@TestEntity", "@TestTable", "@TestId"],
                "imports": [
                    "com.test.persistence.TestEntity",
                    "com.test.persistence.TestTable",
                    "com.test.persistence.TestId",
                ],
            },
            "transactional": {
                "annotations": ["@TestTransactional"],
                "imports": ["com.test.tx.TestTransactional"],
            },
            "rest_endpoint": {
                "annotations": ["@TestPath", "@TestGet", "@TestPost"],
                "imports": [
                    "com.test.ws.TestPath",
                    "com.test.ws.TestGet",
                    "com.test.ws.TestPost",
                ],
            },
            "mock_in_test": {
                "annotations": ["@TestInjectMock"],
                "imports": ["com.test.mock.TestInjectMock"],
            },
        },
        config={},
        test_style=test_style
        or {
            "class_annotations": ["@TestQuarkusTest"],
            "imports": [
                "com.test.junit.TestQuarkusTest",
                "com.test.junit.Test",
                "com.test.junit.Assertions.*",
            ],
            "assertion_library": "junit-jupiter",
        },
        verify_commands={},
        forbidden_imports=forbidden_imports or ["com.forbidden.legacy.*", "org.banned.*"],
        allowed_exceptions=[],
        pitfalls=["Avoid deprecated base classes.", "Fields must not be private in test."],
        templates={},
    )


def test_build_entity_prompt_injects_orm_concepts_and_forbidden_imports():
    from agents.generator.prompt import build_entity_prompt

    profile = _create_sample_profile()
    entity_def = {
        "name": "Customer",
        "tableName": "customers",
        "fields": [
            {"name": "id", "type": "Long", "id": True},
            {"name": "email", "type": "String", "nullable": False},
        ],
    }

    prompt = build_entity_prompt(profile, entity_def)

    # Asserts dynamic injection from profile concepts
    assert "@TestEntity" in prompt
    assert "@TestTable" in prompt
    assert "@TestId" in prompt
    assert "com.test.persistence.TestEntity" in prompt
    assert "com.test.persistence.TestTable" in prompt

    # Asserts forbidden imports injection
    assert "com.forbidden.legacy.*" in prompt
    assert "org.banned.*" in prompt

    # Asserts entity details
    assert "Customer" in prompt
    assert "customers" in prompt
    assert "email" in prompt
    assert "Long" in prompt

    # Asserts raw code instructions (no markdown fences)
    assert "ONLY" in prompt or "raw" in prompt.lower()
    assert "markdown" in prompt.lower()


def test_build_entity_prompt_instructs_no_markdown_blocks():
    from agents.generator.prompt import build_entity_prompt

    profile = _create_sample_profile()
    entity_def = {"name": "Product"}

    prompt = build_entity_prompt(profile, entity_def)

    # Must explicitly prohibit markdown fences
    assert "```" in prompt or "markdown" in prompt.lower()


def test_build_entity_prompt_handles_minimal_entity_def():
    from agents.generator.prompt import build_entity_prompt

    profile = _create_sample_profile()
    entity_def = {"name": "SimpleItem"}

    prompt = build_entity_prompt(profile, entity_def)

    assert "SimpleItem" in prompt
    assert "@TestEntity" in prompt


# --- Gen-2 Repository Prompt Tests ---


def test_build_repository_prompt_injects_transactional_and_forbidden_imports():
    from agents.generator.prompt import build_repository_prompt

    profile = _create_sample_profile()
    entity_def = {
        "name": "Order",
        "tableName": "orders",
        "fields": [{"name": "id", "type": "Long", "id": True}],
    }

    prompt = build_repository_prompt(profile, entity_def)

    # Asserts dynamic injection of transactional concepts
    assert "@TestTransactional" in prompt
    assert "com.test.tx.TestTransactional" in prompt

    # Asserts forbidden imports and pitfalls
    assert "com.forbidden.legacy.*" in prompt
    assert "org.banned.*" in prompt
    assert "Avoid deprecated base classes." in prompt

    # Asserts entity details
    assert "Order" in prompt

    # Asserts raw code instructions
    assert "ONLY" in prompt or "raw" in prompt.lower()
    assert "markdown" in prompt.lower()
    assert "```" in prompt


def test_build_repository_prompt_instructs_no_markdown_fences():
    from agents.generator.prompt import build_repository_prompt

    profile = _create_sample_profile()
    entity_def = {"name": "Invoice"}

    prompt = build_repository_prompt(profile, entity_def)

    assert "markdown" in prompt.lower()
    assert "```" in prompt


# --- Gen-2 Resource Prompt Tests ---


def test_build_resource_prompt_injects_rest_concepts_and_user_stories():
    from agents.generator.prompt import build_resource_prompt

    profile = _create_sample_profile()
    entity_def = {
        "name": "Order",
        "fields": [{"name": "id", "type": "Long"}],
    }
    user_stories = [
        {"title": "Create Order", "description": "Customer creates a new order"},
        "As an admin, I want to cancel an order",
    ]

    prompt = build_resource_prompt(profile, entity_def, user_stories)

    # Asserts dynamic injection of rest_endpoint concepts
    assert "@TestPath" in prompt
    assert "@TestGet" in prompt
    assert "@TestPost" in prompt
    assert "com.test.ws.TestPath" in prompt
    assert "com.test.ws.TestGet" in prompt

    # Asserts user stories injected
    assert "Create Order" in prompt
    assert "Customer creates a new order" in prompt
    assert "As an admin, I want to cancel an order" in prompt

    # Asserts entity name injected
    assert "Order" in prompt

    # Asserts forbidden imports and pitfalls
    assert "com.forbidden.legacy.*" in prompt
    assert "Avoid deprecated base classes." in prompt

    # Asserts raw code instructions
    assert "ONLY" in prompt or "raw" in prompt.lower()
    assert "markdown" in prompt.lower()
    assert "```" in prompt


def test_build_resource_prompt_handles_empty_user_stories():
    from agents.generator.prompt import build_resource_prompt

    profile = _create_sample_profile()
    entity_def = {"name": "Product"}

    prompt = build_resource_prompt(profile, entity_def, [])

    assert "Product" in prompt
    assert "@TestPath" in prompt


# --- Gen-3 Test Prompt Tests ---


def test_build_test_prompt_injects_test_style_and_mock_concepts():
    from agents.generator.prompt import build_test_prompt

    profile = _create_sample_profile()
    user_stories = [
        {"title": "Retrieve Order", "description": "Fetch order details by ID"},
        "Validate invalid order returns 404",
    ]

    prompt = build_test_prompt(
        profile=profile,
        target_class_name="OrderResource",
        class_type="resource",
        user_stories=user_stories,
    )

    # Assert test_style injection
    assert "@TestQuarkusTest" in prompt
    assert "com.test.junit.TestQuarkusTest" in prompt
    assert "com.test.junit.Test" in prompt
    assert "junit-jupiter" in prompt

    # Assert mock_in_test injection
    assert "@TestInjectMock" in prompt
    assert "com.test.mock.TestInjectMock" in prompt

    # Assert target class and type injection
    assert "OrderResource" in prompt
    assert "resource" in prompt.lower()

    # Assert user stories injection
    assert "Retrieve Order" in prompt
    assert "Fetch order details by ID" in prompt
    assert "Validate invalid order returns 404" in prompt

    # Assert forbidden imports and pitfalls
    assert "com.forbidden.legacy.*" in prompt
    assert "Avoid deprecated base classes." in prompt
    assert "Fields must not be private in test." in prompt

    # Assert output directives for ONLY raw Java and NO markdown
    assert "ONLY" in prompt or "raw" in prompt.lower()
    assert "markdown" in prompt.lower()
    assert "```" in prompt


def test_build_test_prompt_handles_repository_class_type():
    from agents.generator.prompt import build_test_prompt

    profile = _create_sample_profile()
    prompt = build_test_prompt(
        profile=profile,
        target_class_name="OrderRepository",
        class_type="repository",
        user_stories=[],
    )

    assert "OrderRepository" in prompt
    assert "repository" in prompt.lower()
    assert "@TestQuarkusTest" in prompt


def test_build_test_prompt_instructs_no_markdown_fences():
    from agents.generator.prompt import build_test_prompt

    profile = _create_sample_profile()
    prompt = build_test_prompt(
        profile=profile,
        target_class_name="CustomerResource",
        class_type="resource",
        user_stories=[],
    )

    assert "markdown" in prompt.lower()
    assert "```" in prompt


def test_build_test_prompt_injects_entity_definition_and_field_constraints():
    from agents.generator.prompt import build_test_prompt

    profile = _create_sample_profile()
    entity_def = {
        "name": "Order",
        "tableName": "orders",
        "fields": [
            {"name": "id", "type": "Long"},
            {"name": "status", "type": "String"},
        ],
    }
    prompt = build_test_prompt(
        profile=profile,
        target_class_name="OrderRepository",
        class_type="repository",
        user_stories=[],
        entity_def=entity_def,
    )

    assert "Entity Definition" in prompt
    assert "Order" in prompt
    assert "status" in prompt
    assert "Entity Field Integrity & Method Constraints" in prompt
    assert "ONLY the exact field names" in prompt


# --- Constitution Rule 8 Static Check ---


def test_prompt_no_hardcoded_framework_literals():
    """Verify Constitution Rule 8: zero framework literals in prompt.py source code."""
    import agents.generator.prompt as prompt_module

    source = inspect.getsource(prompt_module)

    # Prohibited annotations/classes/packages
    forbidden_literals = [
        "@Entity",
        "@Table",
        "@Id",
        "@GeneratedValue",
        "@Column",
        "@Path",
        "@GET",
        "@POST",
        "@PUT",
        "@DELETE",
        "@Produces",
        "@Consumes",
        "@Transactional",
        "@Repository",
        "@RestController",
        "@GetMapping",
        "@PostMapping",
        "@PutMapping",
        "@DeleteMapping",
        "jakarta.persistence",
        "javax.persistence",
        "jakarta.ws.rs",
        "javax.ws.rs",
        "jakarta.transaction",
        "javax.transaction",
        "org.springframework",
        "PanacheEntity",
        "PanacheRepository",
        "@ApplicationScoped",
        "@Inject",
        "@Autowired",
        # Test-specific framework literals
        "@QuarkusTest",
        "@SpringBootTest",
        "@InjectMock",
        "@MockBean",
        "io.quarkus.test",
        "org.springframework.boot.test",
        "org.junit.Test",
        "org.junit.jupiter",
    ]

    for literal in forbidden_literals:
        assert (
            literal not in source
        ), f"Constitution violation: '{literal}' is hardcoded in agents/generator/prompt.py"
