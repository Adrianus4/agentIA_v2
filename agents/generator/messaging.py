from __future__ import annotations

from contracts.models import FileContent
from contracts.solution_models import EventSpec, MicroserviceSpec, ObservabilitySpec

_JAVA_TYPE_IMPORTS = {
    "BigDecimal": "java.math.BigDecimal",
    "UUID": "java.util.UUID",
    "LocalDate": "java.time.LocalDate",
    "LocalDateTime": "java.time.LocalDateTime",
    "Instant": "java.time.Instant",
    "Timestamp": "java.sql.Timestamp",
}


def _to_pascal_event_name(raw_name: str) -> str:
    parts = [p for p in raw_name.replace("-", "_").split("_") if p]
    return "".join(p[0].upper() + p[1:] for p in parts) if parts else "Event"


class MessagingGenerator:
    def generate(
        self,
        service: MicroserviceSpec,
        observability: ObservabilitySpec,
        shared_events: list[EventSpec] | None = None,
    ) -> list[FileContent]:
        combined_events = list(service.events or [])
        if shared_events:
            existing_names = {e.name for e in combined_events}
            for se in shared_events:
                if se.name not in existing_names:
                    combined_events.append(se)

        if service.technical_matrix.messaging != "KAFKA" and not combined_events:
            return []

        package_path = service.package_name.replace(".", "/")
        files: list[FileContent] = []
        trace_header = observability.trace_id_header
        messaging_props: list[str] = [
            "%test.quarkus.kafka.devservices.enabled=false",
        ]

        event_specs = combined_events or [
            EventSpec(
                name=f"{service.service_name.title().replace('-', '')}Event",
                topic=f"{service.service_name}.events",
            )
        ]

        for event in event_specs:
            event_class = _to_pascal_event_name(event.name)
            dto_fields = event.payload_fields or []
            dto_lines: list[str] = []
            required_imports: set[str] = set()
            declared_field_names: set[str] = set()

            for field in dto_fields:
                f_type = field.type.strip()
                f_name = field.name.strip()
                declared_field_names.add(f_name)
                if f_type in _JAVA_TYPE_IMPORTS:
                    required_imports.add(_JAVA_TYPE_IMPORTS[f_type])
                dto_lines.append(f"    public {f_type} {f_name};")

            if "aggregateId" not in declared_field_names:
                dto_lines.append("    public String aggregateId;")
            if "traceId" not in declared_field_names:
                dto_lines.append("    public String traceId;")

            imports_block = ""
            if required_imports:
                imports_block = "\n".join(f"import {imp};" for imp in sorted(required_imports)) + "\n\n"

            files.append(
                FileContent(
                    path=f"src/main/java/{package_path}/events/{event_class}.java",
                    content=(
                        f"package {service.package_name}.events;\n\n"
                        + imports_block
                        + f"public class {event_class} {{\n"
                        + "\n".join(dto_lines)
                        + "\n}\n"
                    ),
                )
            )

            if event.direction in {"PRODUCER", "BIDIRECTIONAL"}:
                out_channel = f"{event.topic}-out"
                messaging_props.extend(
                    [
                        f"mp.messaging.outgoing.{out_channel}.connector=smallrye-kafka",
                        f"mp.messaging.outgoing.{out_channel}.topic={event.topic}",
                    ]
                )
                files.append(
                    FileContent(
                        path=f"src/main/java/{package_path}/messaging/{event_class}Producer.java",
                        content=(
                            f"package {service.package_name}.messaging;\n\n"
                            f"import {service.package_name}.events.{event_class};\n"
                            "import jakarta.enterprise.context.ApplicationScoped;\n"
                            "import jakarta.inject.Inject;\n"
                            "import org.eclipse.microprofile.reactive.messaging.Channel;\n"
                            "import org.eclipse.microprofile.reactive.messaging.Emitter;\n\n"
                            "@ApplicationScoped\n"
                            f"public class {event_class}Producer {{\n\n"
                            f"    @Inject\n    @Channel(\"{out_channel}\")\n    Emitter<{event_class}> emitter;\n\n"
                            f"    public void publish({event_class} event, String traceId) {{\n"
                            "        event.traceId = traceId;\n"
                            "        emitter.send(event);\n"
                            "    }\n"
                            "}\n"
                        ),
                    )
                )

            if event.direction in {"CONSUMER", "BIDIRECTIONAL"}:
                in_channel = f"{event.topic}-in"
                messaging_props.extend(
                    [
                        f"mp.messaging.incoming.{in_channel}.connector=smallrye-kafka",
                        f"mp.messaging.incoming.{in_channel}.topic={event.topic}",
                    ]
                )
                files.append(
                    FileContent(
                        path=f"src/main/java/{package_path}/messaging/{event_class}Consumer.java",
                        content=(
                            f"package {service.package_name}.messaging;\n\n"
                            f"import {service.package_name}.events.{event_class};\n"
                            "import jakarta.enterprise.context.ApplicationScoped;\n"
                            "import org.eclipse.microprofile.reactive.messaging.Incoming;\n"
                            "import org.jboss.logging.Logger;\n\n"
                            "@ApplicationScoped\n"
                            f"public class {event_class}Consumer {{\n"
                            "    private static final Logger LOG = Logger.getLogger(" + f"{event_class}Consumer.class" + ");\n\n"
                            f"    @Incoming(\"{in_channel}\")\n"
                            f"    public void consume({event_class} event) {{\n"
                            f"        LOG.infov(\"Consumed event with {trace_header}={{0}}\", event.traceId);\n"
                            "    }\n"
                            "}\n"
                        ),
                    )
                )

        if len(messaging_props) > 1:
            files.append(
                FileContent(
                    path="src/main/resources/messaging.properties",
                    content="\n".join(messaging_props) + "\n",
                )
            )

        return files
