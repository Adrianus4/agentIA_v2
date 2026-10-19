# Feature Specification: Frontend Feature Parity & Asset Recovery

**Feature Branch**: `010-frontend-rich-inputs`
**Created**: 2026-10-12
**Status**: Ready for Implementation
**Input**: "Achieve frontend feature parity with legacy v1 by recovering official TCS branding, implementing natural language business requirement inputs, detailed Quarkus generator configuration forms, and dual-mode blueprint submission."

## User Scenarios & Testing

### User Story 1 - Official TCS Enterprise Branding (Priority: P1)
As an enterprise user, I want the dashboard to display the official Tata Consultancy Services (TCS) logo and studio identity, so that the application maintains corporate visual consistency with the legacy platform.

**Independent Test**: Mount the `Header` component and verify that the TCS logo image renders with appropriate `alt` text (`Tata Consultancy Services`), high-resolution responsiveness, and proper layout hierarchy.

**Acceptance Scenarios**:
1. **Given** the visual dashboard is loaded, **When** examining the header, **Then** an `<img>` tag is rendered sourcing `/tcs-logo-light.png` (or dark variant) with `alt="Tata Consultancy Services"`.
2. **Given** different screen sizes, **When** scaling from mobile to desktop, **Then** the logo maintains aspect ratio and scales neatly beside the AgentIA v2 identity.

---

### User Story 2 - Natural Language Requirements & Business Rules (Priority: P1)
As a software architect, I want to input natural language business requirements and domain rules for the target microservice, so that the system can synthesize architectural blueprints without requiring manual JSON composition.

**Independent Test**: In the input form, enter natural language prompt text and service metadata, verify that preset templates can be loaded, and verify that the synthesized blueprint contains the expected prompt, service name, and BDD specifications.

**Acceptance Scenarios**:
1. **Given** the input view, **When** the user selects the "Rich Form" mode, **Then** a prominent textarea is available for describing microservice capabilities and business rules.
2. **Given** common enterprise archetypes, **When** selecting quick presets (e.g., Order Service, Payment Service), **Then** default natural language rules and entity definitions pre-populate the form.

---

### User Story 3 - Detailed Quarkus Generator Configuration (Priority: P1)
As a cloud-native developer, I want to configure Quarkus-specific generation options (extensions, build tool, Java version, database engine, architecture pattern), so that the synthesized project matches enterprise cloud-native standards.

**Independent Test**: Toggle various Quarkus options (e.g. database = POSTGRESQL, build_tool = maven, extensions = [quarkus-rest, quarkus-hibernate-orm]), and verify that the resulting payload reflects all selected configuration parameters.

**Acceptance Scenarios**:
1. **Given** the Quarkus configuration section, **When** selecting target database (`POSTGRESQL`, `MYSQL`, `H2`), **Then** the blueprint configuration updates the database engine accordingly.
2. **Given** Quarkus extensions selection, **When** checking or unchecking extensions (`quarkus-rest`, `quarkus-hibernate-orm`, `quarkus-smallrye-openapi`, etc.), **Then** the extensions array is accurately updated.
3. **Given** architecture pattern preferences (`layered`, `hexagonal`, `hexagonal-ddd`), **When** selected, **Then** the blueprint architecture metadata is set.

---

### User Story 4 - Dual-Mode Blueprint Synchronization & Dispatch (Priority: P1)
As an operator, I want to seamlessly switch between the Rich Form UI and the Raw Blueprint JSON editor, so that I can inspect or fine-tune generated JSON while enjoying rich guided input.

**Independent Test**: Edit fields in the Rich Form, switch to the Raw JSON tab and verify that the JSON is updated; switch back and verify data integrity; submit and verify `POST /v1/blueprint/run` receives the unified payload.

**Acceptance Scenarios**:
1. **Given** changes made in the Rich Form, **When** switching to the JSON Blueprint tab, **Then** the JSON representation reflects the current form state in real-time.
2. **Given** either tab active, **When** clicking "Run Orchestrator", **Then** the request is dispatched to `POST /v1/blueprint/run` with the configured workspace directory and API credentials.

