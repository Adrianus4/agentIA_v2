from __future__ import annotations

from contracts.models import FileContent
from contracts.solution_models import MicroserviceSpec


class OutboxGenerator:
    def generate(self, service: MicroserviceSpec) -> list[FileContent]:
        if service.technical_matrix.messaging != "KAFKA" and not service.events:
            return []

        package_path = service.package_name.replace(".", "/")
        entity_name = "OutboxEvent"
        repository_name = "OutboxEventRepository"
        relay_name = "OutboxRelayService"

        entity_content = (
            f"package {service.package_name}.outbox;\n\n"
            "import jakarta.persistence.Column;\n"
            "import jakarta.persistence.Entity;\n"
            "import jakarta.persistence.GeneratedValue;\n"
            "import jakarta.persistence.GenerationType;\n"
            "import jakarta.persistence.Id;\n"
            "import jakarta.persistence.Table;\n"
            "import java.time.Instant;\n\n"
            "@Entity\n"
            "@Table(name = \"outbox_events\")\n"
            f"public class {entity_name} {{\n"
            "    @Id\n"
            "    @GeneratedValue(strategy = GenerationType.IDENTITY)\n"
            "    public Long id;\n"
            "    @Column(nullable = false, unique = true)\n"
            "    public String eventId;\n"
            "    @Column(nullable = false)\n"
            "    public String aggregateType;\n"
            "    @Column(nullable = false)\n"
            "    public String aggregateId;\n"
            "    @Column(nullable = false)\n"
            "    public String eventType;\n"
            "    @Column(nullable = false, length = 4000)\n"
            "    public String payload;\n"
            "    @Column(nullable = false)\n"
            "    public String traceId;\n"
            "    @Column(nullable = false)\n"
            "    public boolean processed = false;\n"
            "    @Column(nullable = false)\n"
            "    public Instant createdAt = Instant.now();\n"
            "}\n"
        )

        repo_content = (
            f"package {service.package_name}.outbox;\n\n"
            "import io.quarkus.hibernate.orm.panache.PanacheRepository;\n"
            "import jakarta.enterprise.context.ApplicationScoped;\n"
            "import java.util.List;\n\n"
            "@ApplicationScoped\n"
            f"public class {repository_name} implements PanacheRepository<{entity_name}> {{\n"
            f"    public List<{entity_name}> findUnprocessed() {{\n"
            "        return list(\"processed\", false);\n"
            "    }\n\n"
            "    public boolean existsByEventId(String eventId) {\n"
            "        return count(\"eventId\", eventId) > 0;\n"
            "    }\n"
            "}\n"
        )

        relay_content = (
            f"package {service.package_name}.outbox;\n\n"
            "import jakarta.enterprise.context.ApplicationScoped;\n"
            "import jakarta.inject.Inject;\n"
            "import jakarta.transaction.Transactional;\n"
            "import java.util.List;\n"
            "import java.util.UUID;\n\n"
            "@ApplicationScoped\n"
            f"public class {relay_name} {{\n\n"
            "    @Inject\n"
            f"    {repository_name} repository;\n\n"
            "    @Transactional\n"
            f"    public {entity_name} recordEvent(String aggregateType, String aggregateId, String eventType, String payload, String traceId) {{\n"
            "        String dedupKey = aggregateType + \":\" + aggregateId + \":\" + eventType + \":\" + (traceId != null ? traceId : UUID.randomUUID().toString());\n"
            "        if (repository.existsByEventId(dedupKey)) {\n"
            "            return repository.find(\"eventId\", dedupKey).firstResult();\n"
            "        }\n"
            f"        {entity_name} evt = new {entity_name}();\n"
            "        evt.eventId = dedupKey;\n"
            "        evt.aggregateType = aggregateType;\n"
            "        evt.aggregateId = aggregateId;\n"
            "        evt.eventType = eventType;\n"
            "        evt.payload = payload;\n"
            "        evt.traceId = traceId != null ? traceId : UUID.randomUUID().toString();\n"
            "        evt.processed = false;\n"
            "        repository.persist(evt);\n"
            "        return evt;\n"
            "    }\n\n"
            "    @Transactional\n"
            "    public int relayPendingEvents() {\n"
            f"        List<{entity_name}> pending = repository.findUnprocessed();\n"
            f"        for ({entity_name} evt : pending) {{\n"
            "            evt.processed = true;\n"
            "        }\n"
            "        return pending.size();\n"
            "    }\n"
            "}\n"
        )

        return [
            FileContent(path=f"src/main/java/{package_path}/outbox/{entity_name}.java", content=entity_content),
            FileContent(path=f"src/main/java/{package_path}/outbox/{repository_name}.java", content=repo_content),
            FileContent(path=f"src/main/java/{package_path}/outbox/{relay_name}.java", content=relay_content),
        ]
