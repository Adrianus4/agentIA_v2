# Checklist: 010-frontend-rich-inputs

- [ ] **Asset Recovery**: TCS logo files (`tcs-logo-light.png`, `tcs-logo-dark.png`, `tcs-logo.png`) located and copied to `frontend/public/` and `frontend/src/assets/`.
- [ ] **Header Branding**: `Header.tsx` renders actual TCS logo `<img>` alongside AgentIA v2 identity.
- [ ] **Natural Language Requirements Input**: Textarea for business rules and capabilities with sample presets.
- [ ] **Quarkus Configuration Inputs**:
  - [ ] Framework: Quarkus (with Spring Boot option)
  - [ ] Java Version: Java 21 / Java 17
  - [ ] Build Tool: Maven / Gradle
  - [ ] Database: PostgreSQL / MySQL / H2
  - [ ] Architecture Style: Layered (4 capas) / Hexagonal / Hexagonal-DDD
  - [ ] Quarkus Extensions: Multi-select for `quarkus-rest`, `quarkus-rest-jackson`, `quarkus-hibernate-orm`, `quarkus-hibernate-validator`, `quarkus-smallrye-openapi`, `quarkus-smallrye-health`
- [ ] **Dual-Mode Editor**: Tabbed interface between Rich Form and Raw JSON editor.
- [ ] **Payload Synchronization**: Form values correctly build and map to the backend `BlueprintRequest.blueprint` schema.
- [ ] **Automated Tests**: Unit and integration tests for rich input controls, logo rendering, and form submission pass cleanly (`npm test`).

