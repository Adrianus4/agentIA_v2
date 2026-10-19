from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.generator import EntityGenerator, ResourceGenerator, TestGenerator
from agents.profiles.loader import get_profile
from agents.scaffolder.extensions import derive_extensions
from app.core.llm.factory import build_llm_client
from contracts.models import FileContent, FrameworkProfile, GenerationRequest


def _resolve_bom_version(blueprint: dict[str, Any], profile: FrameworkProfile) -> str:
    """Resolve concrete Maven BOM version from blueprint or profile scaffold configuration."""
    bp_ver = str(blueprint.get("frameworkVersion") or blueprint.get("version") or "").strip()
    if bp_ver.count(".") >= 2 and not bp_ver.endswith(".Final"):
        return bp_ver
    if profile.scaffold and profile.scaffold.tool_version and "." in profile.scaffold.tool_version:
        return profile.scaffold.tool_version
    if profile.framework_version.count(".") >= 2:
        return profile.framework_version
    return "3.15.1"


def _extension_to_dependency_xml(coord: str) -> str:
    """Convert a 'groupId:artifactId' coordinate into a Maven <dependency> XML block."""
    if ":" in coord:
        group_id, artifact_id = coord.split(":", 1)
    else:
        group_id, artifact_id = "io.quarkus", coord
    return (
        "        <dependency>\n"
        f"            <groupId>{group_id.strip()}</groupId>\n"
        f"            <artifactId>{artifact_id.strip()}</artifactId>\n"
        "        </dependency>"
    )


class _LazyLLMClient:
    """Builds the LLM client on first use, so template-only generation needs no LLM at all."""

    def __init__(self, **settings: Any) -> None:
        self._settings = settings
        self._client: Any = None

    def generate(self, prompt: str, **kwargs: Any) -> Any:
        if self._client is None:
            self._client = build_llm_client(**self._settings)
        return self._client.generate(prompt, **kwargs)


class GenerationPipeline:
    """Generate the application source tree from one validated blueprint."""

    def __init__(self, llm_client: Any | None = None, profiles_dir: str | Path | None = None) -> None:
        self.llm_client = llm_client
        self.profiles_dir = profiles_dir
        self.entity_generator = EntityGenerator()
        self.resource_generator = ResourceGenerator()
        self.test_generator = TestGenerator()

    def __call__(self, request: GenerationRequest, state: Any = None) -> list[FileContent]:
        del state
        blueprint = request.blueprint
        llm_client: Any = self.llm_client
        if llm_client is None:
            llm = request.llm
            llm_client = _LazyLLMClient(
                provider=llm.provider if llm else None,
                model=llm.model if llm else None,
                endpoint=llm.endpoint if llm else None,
                api_key=llm.api_key if llm else None,
            )

        profile = self._profile_for(blueprint)
        files: list[FileContent] = []
        files.extend(self.entity_generator.generate(request, profile, llm_client))
        files.extend(self.resource_generator.generate(request, profile, llm_client))
        files.extend(self.test_generator.generate(request, profile, llm_client))

        if not any(f.path == "pom.xml" for f in files):
            files.append(self._generate_pom(blueprint, profile))
        if not any("application.properties" in f.path for f in files):
            files.append(self._generate_application_properties(blueprint, profile))

        return files

    def _generate_pom(self, blueprint: dict[str, Any], profile: FrameworkProfile) -> FileContent:
        artifact_id = (
            str(blueprint.get("serviceName") or blueprint.get("name") or "microservice")
            .lower()
            .replace(" ", "-")
        )
        group_id = str(blueprint.get("groupId") or blueprint.get("packageName") or "com.tcs.agentia")
        java_version = str(blueprint.get("javaVersion") or profile.java_version or "21")
        bom_version = _resolve_bom_version(blueprint, profile)

        if profile.scaffold is not None:
            extensions = derive_extensions(blueprint, profile)
        else:
            extensions = [
                "io.quarkus:quarkus-arc",
                "io.quarkus:quarkus-rest-jackson",
                "io.quarkus:quarkus-hibernate-orm-panache",
                "io.quarkus:quarkus-hibernate-validator",
                "io.quarkus:quarkus-jdbc-postgresql",
            ]

        dependencies_xml = "\n".join(_extension_to_dependency_xml(ext) for ext in extensions)
        test_h2_xml = ""
        if not any("quarkus-jdbc-h2" in ext for ext in extensions):
            test_h2_xml = """        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-jdbc-h2</artifactId>
            <scope>test</scope>
        </dependency>\n"""

        pom_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>{group_id}</groupId>
    <artifactId>{artifact_id}</artifactId>
    <version>1.0.0-SNAPSHOT</version>

    <properties>
        <compiler-plugin.version>3.13.0</compiler-plugin.version>
        <maven.compiler.release>{java_version}</maven.compiler.release>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <project.reporting.outputEncoding>UTF-8</project.reporting.outputEncoding>
        <quarkus.platform.artifact-id>quarkus-bom</quarkus.platform.artifact-id>
        <quarkus.platform.group-id>io.quarkus.platform</quarkus.platform.group-id>
        <quarkus.platform.version>{bom_version}</quarkus.platform.version>
        <surefire-plugin.version>3.3.1</surefire-plugin.version>
    </properties>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>${{quarkus.platform.group-id}}</groupId>
                <artifactId>${{quarkus.platform.artifact-id}}</artifactId>
                <version>${{quarkus.platform.version}}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>

    <dependencies>
{dependencies_xml}
{test_h2_xml}        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-junit5</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.rest-assured</groupId>
            <artifactId>rest-assured</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>${{quarkus.platform.group-id}}</groupId>
                <artifactId>quarkus-maven-plugin</artifactId>
                <version>${{quarkus.platform.version}}</version>
                <extensions>true</extensions>
                <executions>
                    <execution>
                        <goals>
                            <goal>build</goal>
                            <goal>generate-code</goal>
                            <goal>generate-code-tests</goal>
                        </goals>
                    </execution>
                </executions>
            </plugin>
            <plugin>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>${{compiler-plugin.version}}</version>
                <configuration>
                    <compilerArgs>
                        <arg>-parameters</arg>
                    </compilerArgs>
                </configuration>
            </plugin>
            <plugin>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>${{surefire-plugin.version}}</version>
                <configuration>
                    <systemPropertyVariables>
                        <java.util.logging.manager>org.jboss.logmanager.LogManager</java.util.logging.manager>
                    </systemPropertyVariables>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""
        return FileContent(path="pom.xml", content=pom_content)

    def _generate_application_properties(
        self,
        blueprint: dict[str, Any],
        profile: FrameworkProfile | None = None,
    ) -> FileContent:
        service_name = (
            str(blueprint.get("serviceName") or blueprint.get("name") or "microservice")
            .lower()
            .replace(" ", "-")
        )
        db_name = service_name.replace("-", "_")
        params = blueprint.get("parameters") or {}
        raw_db = str(
            blueprint.get("database")
            or blueprint.get("databaseType")
            or blueprint.get("databaseEngine")
            or params.get("database", "POSTGRESQL")
        ).lower()
        db_kind = "postgresql" if "postgres" in raw_db else "mysql" if "mysql" in raw_db else "h2"
        messaging = str(
            blueprint.get("messaging")
            or blueprint.get("messagingSystem")
            or params.get("messaging", "NONE")
        ).upper()

        profile_props = (profile.config.get("properties") if profile and isinstance(profile.config, dict) else None) or {}
        http_port = profile_props.get("quarkus.http.port", 8080)
        log_level = profile_props.get("quarkus.log.level", "INFO")

        if db_kind == "postgresql":
            default_jdbc_url = f"jdbc:postgresql://localhost:5432/{db_name}"
            default_user = "postgres"
            default_pass = "postgres"
        elif db_kind == "mysql":
            default_jdbc_url = f"jdbc:mysql://localhost:3306/{db_name}"
            default_user = "root"
            default_pass = "root"
        else:
            default_jdbc_url = f"jdbc:h2:mem:{db_name};DB_CLOSE_DELAY=-1"
            default_user = "sa"
            default_pass = "sa"

        # Use in-memory H2 for %test so hermetic `mvn -B test` runs without requiring a live PostgreSQL/MySQL server
        test_jdbc_url = f"jdbc:h2:mem:{db_name}_test;DB_CLOSE_DELAY=-1"

        content = f"""quarkus.application.name={service_name}
quarkus.http.port={http_port}
quarkus.log.level={log_level}
quarkus.datasource.db-kind={db_kind}
%test.quarkus.datasource.db-kind=h2

# Datasource connection settings per profile
%dev.quarkus.datasource.jdbc.url=${{DB_JDBC_URL:{default_jdbc_url}}}
%dev.quarkus.datasource.username=${{DB_USERNAME:{default_user}}}
%dev.quarkus.datasource.password=${{DB_PASSWORD:{default_pass}}}

%test.quarkus.datasource.jdbc.url=${{TEST_DB_JDBC_URL:{test_jdbc_url}}}
%test.quarkus.datasource.username=${{TEST_DB_USERNAME:sa}}
%test.quarkus.datasource.password=${{TEST_DB_PASSWORD:sa}}

%prod.quarkus.datasource.jdbc.url=${{DB_JDBC_URL:{default_jdbc_url}}}
%prod.quarkus.datasource.username=${{DB_USERNAME:{default_user}}}
%prod.quarkus.datasource.password=${{DB_PASSWORD:{default_pass}}}

# Database schema management per environment (never drop-and-create in production)
%dev.quarkus.hibernate-orm.database.generation=drop-and-create
%test.quarkus.hibernate-orm.database.generation=drop-and-create
%prod.quarkus.hibernate-orm.database.generation=${{DB_SCHEMA_GENERATION:validate}}
"""
        if "KAFKA" in messaging or blueprint.get("events"):
            content += """
# Reactive Messaging Kafka configuration
%dev.kafka.bootstrap.servers=localhost:9092
%test.kafka.bootstrap.servers=localhost:9092
%test.quarkus.kafka.devservices.enabled=false
%prod.kafka.bootstrap.servers=${KAFKA_BOOTSTRAP_SERVERS:localhost:9092}
"""
        config_path = (
            str(profile.config.get("file_path"))
            if profile and isinstance(profile.config, dict) and profile.config.get("file_path")
            else "src/main/resources/application.properties"
        )
        return FileContent(path=config_path, content=content)

    def _profile_for(self, blueprint: dict[str, Any]) -> FrameworkProfile:
        framework = str(blueprint.get("framework", "quarkus"))
        version = str(blueprint.get("version", blueprint.get("frameworkVersion", "3.15")))
        try:
            return get_profile(framework, version, self.profiles_dir)
        except Exception:
            return get_profile(framework, "3", self.profiles_dir)