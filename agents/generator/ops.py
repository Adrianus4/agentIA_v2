from __future__ import annotations

from contracts.models import FileContent
from contracts.solution_models import MicroserviceSpec, ObservabilitySpec, SecuritySpec


class ObservabilityGenerator:
    def generate(self, service: MicroserviceSpec, observability: ObservabilitySpec) -> list[FileContent]:
        if not observability.enabled:
            return []

        package_path = service.package_name.replace(".", "/")
        header = observability.trace_id_header
        config_lines = [
            "quarkus.smallrye-health.root-path=/q/health",
        ]
        if observability.structured_logging:
            config_lines.append(
                'quarkus.log.console.format={"timestamp":"%d{yyyy-MM-dd\'T\'HH:mm:ss.SSSZ}","level":"%p","service":"'
                + service.service_name
                + '","logger":"%c{2.}","thread":"%t","message":"%s%e"}%n'
            )
        if observability.metrics:
            config_lines.extend(
                [
                    "quarkus.micrometer.enabled=true",
                    "quarkus.micrometer.export.prometheus.enabled=true",
                    "quarkus.micrometer.export.prometheus.path=/q/metrics",
                ]
            )
        if observability.tracing:
            config_lines.extend(
                [
                    "quarkus.otel.enabled=true",
                    "quarkus.otel.traces.exporter=${OTEL_TRACES_EXPORTER:cdi}",
                    "quarkus.otel.exporter.otlp.traces.endpoint=${OTEL_EXPORTER_OTLP_ENDPOINT:http://localhost:4317}",
                    "%test.quarkus.otel.sdk.disabled=true",
                ]
            )

        filter_content = (
            f"package {service.package_name}.observability;\n\n"
            "import io.quarkus.logging.Log;\n"
            "import jakarta.ws.rs.container.ContainerRequestContext;\n"
            "import jakarta.ws.rs.container.ContainerRequestFilter;\n"
            "import jakarta.ws.rs.container.ContainerResponseContext;\n"
            "import jakarta.ws.rs.container.ContainerResponseFilter;\n"
            "import jakarta.ws.rs.ext.Provider;\n"
            "import java.util.UUID;\n\n"
            "@Provider\n"
            "public class TraceFilter implements ContainerRequestFilter, ContainerResponseFilter {\n"
            f"    public static final String TRACE_HEADER = \"{header}\";\n"
            "    private static final String TRACE_PROP = \"agentia.trace_id\";\n\n"
            "    @Override\n"
            "    public void filter(ContainerRequestContext requestContext) {\n"
            "        String traceId = requestContext.getHeaderString(TRACE_HEADER);\n"
            "        if (traceId == null || traceId.isBlank()) {\n"
            "            traceId = UUID.randomUUID().toString();\n"
            "        }\n"
            "        requestContext.setProperty(TRACE_PROP, traceId);\n"
            "        Log.infov(\"trace_id={0}\", traceId);\n"
            "    }\n\n"
            "    @Override\n"
            "    public void filter(ContainerRequestContext requestContext, ContainerResponseContext responseContext) {\n"
            "        Object prop = requestContext.getProperty(TRACE_PROP);\n"
            "        String traceId = prop != null ? prop.toString() : requestContext.getHeaderString(TRACE_HEADER);\n"
            "        if (traceId == null || traceId.isBlank()) {\n"
            "            traceId = UUID.randomUUID().toString();\n"
            "        }\n"
            "        responseContext.getHeaders().putSingle(TRACE_HEADER, traceId);\n"
            "    }\n"
            "}\n"
        )

        return [
            FileContent(path=f"src/main/java/{package_path}/observability/TraceFilter.java", content=filter_content),
            FileContent(path="src/main/resources/observability.properties", content="\n".join(config_lines) + "\n"),
        ]


class SecurityGenerator:
    def generate(self, service: MicroserviceSpec, security: SecuritySpec) -> list[FileContent]:
        if not security.enabled or security.mode == "NONE":
            return []

        package_path = service.package_name.replace(".", "/")
        role = security.roles[0] if security.roles else "user"
        api_policy = "authenticated" if getattr(security, "protect_api", False) else "permit"
        extension_lines = [
            "quarkus.http.auth.proactive=true",
            "quarkus.http.auth.permission.internal.paths=/internal/*",
            "quarkus.http.auth.permission.internal.policy=authenticated",
            "quarkus.http.auth.permission.health.paths=/q/*",
            "quarkus.http.auth.permission.health.policy=permit",
            "quarkus.http.auth.permission.api.paths=/api/*",
            f"quarkus.http.auth.permission.api.policy=${{API_AUTH_POLICY:{api_policy}}}",
        ]
        if security.mode == "JWT":
            extension_lines.extend(
                [
                    "mp.jwt.verify.issuer=${JWT_ISSUER:https://agentia.tcs.local/issuer}",
                ]
            )
        elif security.mode == "OIDC":
            extension_lines.extend(
                [
                    "quarkus.oidc.application-type=service",
                    "%dev.quarkus.oidc.enabled=false",
                    "%test.quarkus.oidc.enabled=false",
                    "%prod.quarkus.oidc.auth-server-url=${OIDC_AUTH_SERVER_URL:http://localhost:8180/realms/agentia}",
                ]
            )
        elif security.mode == "API_KEY":
            extension_lines.extend(
                [
                    "agentia.security.api-key=${SERVICE_API_KEY:change-me}",
                ]
            )

        secured_resource = (
            f"package {service.package_name}.security;\n\n"
            "import jakarta.annotation.security.RolesAllowed;\n"
            "import jakarta.ws.rs.GET;\n"
            "import jakarta.ws.rs.Path;\n\n"
            "@Path(\"/internal/security-check\")\n"
            "public class SecurityCheckResource {\n"
            f"    @GET\n    @RolesAllowed(\"{role}\")\n"
            "    public String check() {\n"
            f"        return \"secured:{service.service_name}\";\n"
            "    }\n"
            "}\n"
        )

        return [
            FileContent(path=f"src/main/java/{package_path}/security/SecurityCheckResource.java", content=secured_resource),
            FileContent(path="src/main/resources/security.properties", content="\n".join(extension_lines) + "\n"),
        ]
