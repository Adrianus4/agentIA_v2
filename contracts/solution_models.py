from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from contracts.models import (
    DomainModel,
    FieldSpec,
    FileContent,
    LLMConfiguration,
    TechnicalMatrix,
    UserStory,
    VerificationResult,
)


class ApiEndpointSpec(BaseModel):
    name: str = Field(min_length=1)
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = "GET"
    path: str = Field(min_length=1)
    description: str | None = None


class EventSpec(BaseModel):
    name: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    direction: Literal["PRODUCER", "CONSUMER", "BIDIRECTIONAL"] = "PRODUCER"
    payload_fields: list[FieldSpec] = []
    description: str | None = None


class ObservabilitySpec(BaseModel):
    enabled: bool = True
    health: bool = True
    metrics: bool = True
    tracing: bool = True
    structured_logging: bool = True
    trace_id_header: str = "X-Trace-Id"


class SecuritySpec(BaseModel):
    enabled: bool = True
    mode: Literal["JWT", "OIDC", "API_KEY", "NONE"] = "JWT"
    service_to_service_auth: bool = True
    protect_api: bool = False
    roles: list[str] = []


class DeploymentSpec(BaseModel):
    docker: bool = True
    kubernetes: bool = True
    openshift: bool = False
    base_image: str = "registry.access.redhat.com/ubi9/openjdk-21-runtime"
    replicas: int = Field(default=1, ge=1)
    namespace: str = "default"


class MicroserviceSpec(BaseModel):
    service_name: str = Field(min_length=1)
    package_name: str = Field(min_length=1)
    business_objective: str | None = None
    technical_matrix: TechnicalMatrix = Field(default_factory=TechnicalMatrix)
    user_stories: list[UserStory] = []
    domain_models: list[DomainModel] = []
    api_endpoints: list[ApiEndpointSpec] = []
    events: list[EventSpec] = []
    depends_on: list[str] = []
    workspace_dir: str | None = None

    def to_generation_blueprint(
        self,
        observability: ObservabilitySpec | None = None,
        security: SecuritySpec | None = None,
    ) -> dict[str, Any]:
        entities = [
            {
                "name": model.name,
                "tableName": model.table_name,
                "fields": [
                    {
                        "name": field.name,
                        "type": field.type,
                        "nullable": field.nullable,
                        "validationRules": field.constraints,
                        "primaryKey": field.name.lower() == "id",
                    }
                    for field in model.fields
                ],
            }
            for model in self.domain_models
        ]
        bp: dict[str, Any] = {
            "name": self.service_name,
            "serviceName": self.service_name,
            "packageName": self.package_name,
            "entities": entities,
            "userStories": [story.model_dump() for story in self.user_stories],
            "parameters": {
                "database": self.technical_matrix.database,
                "messaging": self.technical_matrix.messaging,
                "requirementsSize": self.technical_matrix.scope,
                "workspaceDir": self.workspace_dir,
            },
            "apiEndpoints": [endpoint.model_dump() for endpoint in self.api_endpoints],
            "events": [event.model_dump() for event in self.events],
            "dependsOn": self.depends_on,
        }
        if observability is not None:
            bp["observability"] = observability.model_dump()
        if security is not None:
            bp["security"] = security.model_dump()
        return bp


class SolutionBlueprint(BaseModel):
    name: str = Field(min_length=1)
    business_objective: str | None = None
    services: list[MicroserviceSpec]
    shared_events: list[EventSpec] = []
    deployment: DeploymentSpec = Field(default_factory=DeploymentSpec)
    observability: ObservabilitySpec = Field(default_factory=ObservabilitySpec)
    security: SecuritySpec = Field(default_factory=SecuritySpec)

    @field_validator("services")
    @classmethod
    def validate_non_empty_services(cls, value: list[MicroserviceSpec]) -> list[MicroserviceSpec]:
        if not value:
            raise ValueError("SolutionBlueprint must define at least one service")
        return value

    @model_validator(mode="after")
    def validate_solution_has_services(self) -> SolutionBlueprint:
        if not getattr(self, "services", None):
            raise ValueError("SolutionBlueprint must define at least one service")
        return self


class GeneratedServiceArtifact(BaseModel):
    service_name: str = Field(min_length=1)
    workspace_dir: str = Field(min_length=1)
    files: list[FileContent] = []
    status: Literal["GENERATED", "TESTED", "VERIFIED", "FAILED"] = "GENERATED"
    verification: VerificationResult | None = None


class SolutionGenerationRequest(BaseModel):
    solution: SolutionBlueprint
    trace_id: str | None = None
    llm: LLMConfiguration | None = None


class SolutionGenerationResult(BaseModel):
    trace_id: str | None = None
    solution_name: str = Field(min_length=1)
    status: Literal["GENERATED", "TESTED", "VERIFIED", "SUCCESS", "FAILED", "NO_FIX"] = "GENERATED"
    outcome: Literal["GENERATED", "TESTED", "VERIFIED", "SUCCESS", "FAILED", "NO_FIX"] = "GENERATED"
    services: list[GeneratedServiceArtifact] = []
    manifest: list[FileContent] = []
