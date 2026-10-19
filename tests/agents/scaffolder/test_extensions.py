import pytest

from agents.profiles.loader import get_profile
from agents.scaffolder.extensions import derive_extensions


def test_derive_extensions_is_sorted_deduplicated_and_profile_owned() -> None:
    profile = get_profile("quarkus", "3")
    blueprint = {
        "entities": [{"name": "Invoice"}],
        "database": "postgresql",
        "validation": True,
    }

    first = derive_extensions(blueprint, profile)
    second = derive_extensions(blueprint, profile)

    assert first == second == sorted(set(first))
    assert "io.quarkus:quarkus-hibernate-orm-panache" in first
    assert "io.quarkus:quarkus-jdbc-postgresql" in first
    assert "io.quarkus:quarkus-hibernate-validator" in first
    assert "io.quarkus:quarkus-smallrye-reactive-messaging-kafka" not in first


def test_derive_extensions_includes_kafka_and_mysql_only_when_requested() -> None:
    profile = get_profile("quarkus", "3.15")
    blueprint = {
        "entities": [{"name": "Order"}],
        "parameters": {"database": "MYSQL", "messaging": "KAFKA"},
    }

    extensions = derive_extensions(blueprint, profile)
    assert "io.quarkus:quarkus-jdbc-mysql" in extensions
    assert "io.quarkus:quarkus-jdbc-postgresql" not in extensions
    assert "io.quarkus:quarkus-smallrye-reactive-messaging-kafka" in extensions


def test_derive_extensions_rejects_unknown_database_feature() -> None:
    profile = get_profile("quarkus", "3.15")
    blueprint = {
        "entities": [{"name": "Order"}],
        "database": "cosmosdb",
    }

    with pytest.raises(ValueError, match="unsupported extension feature"):
        derive_extensions(blueprint, profile)
