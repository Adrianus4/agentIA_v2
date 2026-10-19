# Directivas de Negocio en Texto Plano (Text Description Inputs)
**AgentIA Studio • Quarkus 3.x Reactive Generator**

Este documento contiene las **descripciones en lenguaje natural (Directivas de Negocio / PMO Prompts)** para copiar y pegar directamente en el área de texto de **AgentIA Studio** (*Tab 0: "Directiva de Negocio o Comando del PMO"* o en el botón *"Estructurar con IA"*).

---

## Índice Rápido
1. [Ejemplo 1: E-Commerce Order & Fulfillment Service](#ejemplo-1-e-commerce-order--fulfillment-service)
2. [Ejemplo 2: Financial Escrow & Settlement Service](#ejemplo-2-financial-escrow--settlement-service)
3. [Ejemplo 3: Industrial IoT Telemetry Ingestion Service](#ejemplo-3-industrial-iot-telemetry-ingestion-service)
4. [Ejemplo 4: Banking Customer KYC & Compliance Service](#ejemplo-4-banking-customer-kyc--compliance-service)
5. [Ejemplo 5: Agile Task Tracker & Sprint Workflow Service](#ejemplo-5-agile-task-tracker--sprint-workflow-service)

---

## Ejemplo 1: E-Commerce Order & Fulfillment Service

### Texto para Copiar y Pegar en la UI:
```text
Crear un microservicio reactivo en Quarkus 3.15 llamado order-service bajo el paquete com.tcs.agentia.order para gestionar órdenes de compra y facturación electrónica.

Requisitos de Dominio:
- Entidad principal PurchaseOrder mapeada a la tabla purchase_orders en PostgreSQL.
- Clave primaria id de tipo UUID generada automáticamente.
- Campos requeridos: customerEmail (tipo String, con validación @Email y @NotNull), totalAmount (tipo BigDecimal, validación @Positive y @NotNull), status (tipo String con valor inicial PENDING_PAYMENT) y createdAt (tipo Instant con marca temporal automática).

Operaciones REST y Mensajería:
- Endpoint POST /api/orders para registrar una nueva orden validando que el monto sea mayor a 0 y retornando HTTP 201 Created con el ID asignado.
- Endpoint GET /api/orders/{id} para consultar el estado actual de la orden retornando HTTP 200 OK o HTTP 404 Not Found si no existe.
- Endpoint GET /api/orders para listar las órdenes de forma reactiva con paginación.
- Publicar evento a tópico Kafka 'order-events' cuando la orden cambia al estado CONFIRMED.
- Persistencia reactiva con Hibernate Reactive Panache y PostgreSQL.
```

* **Servicio:** `order-service`
* **Base de Datos:** `POSTGRESQL`
* **Mensajería:** `KAFKA`
* **Entidad generada:** `PurchaseOrder` (PK: UUID)

---

## Ejemplo 2: Financial Escrow & Settlement Service

### Texto para Copiar y Pegar en la UI:
```text
Desarrollar un microservicio financiero de custodia y liquidación de pagos en garantía (Escrow) llamado payment-escrow-service bajo el paquete com.tcs.agentia.escrow con persistencia transaccional ACID en PostgreSQL.

Requisitos de Dominio:
- Entidad principal EscrowContract mapeada a la tabla escrow_contracts.
- Clave primaria id de tipo Long autoincremental (@GeneratedValue(strategy = GenerationType.IDENTITY)).
- Campos requeridos: contractCode (tipo String, único y obligatorio, con regla de negocio @NotBlank), heldAmount (tipo BigDecimal, monto en custodia obligatorio y positivo @Positive), buyerAccount (tipo String obligatorio), sellerAccount (tipo String obligatorio), status (tipo String con estados: HELD, RELEASED, REFUNDED) y createdAt (tipo Instant).

Reglas de Negocio y Endpoints:
- Endpoint POST /api/escrow/contracts para aperturar un contrato de custodia reteniendo los fondos con estado inicial HELD.
- Endpoint PUT /api/escrow/contracts/{id}/release para liberar los fondos en favor del vendedor (cambia estado a RELEASED bajo transacción ACID).
- Endpoint PUT /api/escrow/contracts/{id}/refund para reembolsar los fondos al comprador (cambia estado a REFUNDED).
- Endpoint GET /api/escrow/contracts/{id} para auditoría y consulta de contrato.
- Debe incluir control estricto de concurrencia y validación con Hibernate Validator.
```

* **Servicio:** `payment-escrow-service`
* **Base de Datos:** `POSTGRESQL`
* **Mensajería:** `NONE`
* **Entidad generada:** `EscrowContract` (PK: Long)

---

## Ejemplo 3: Industrial IoT Telemetry Ingestion Service

### Texto para Copiar y Pegar en la UI:
```text
Construir un microservicio de ingesta masiva de telemetría y sensores industriales IoT llamado telemetry-service bajo el paquete com.tcs.agentia.telemetry utilizando Quarkus reactivo y base de datos MySQL.

Requisitos de Dominio:
- Entidad principal TelemetryReading mapeada a la tabla telemetry_readings.
- Clave primaria id de tipo UUID.
- Atributos: deviceId (tipo String, identificador único de sensor, no nulo), temperature (tipo Double, lectura en grados Celsius), humidity (tipo Double, porcentaje 0-100 con validación de rango), pressure (tipo Double, presión barométrica en hPa) y recordedAt (tipo Instant, marca temporal de la lectura).

Capacidades Reactivas y Endpoints:
- Endpoint POST /api/telemetry/ingest optimizado para alta tasa de ingestión reactiva (Uni<Response>) recibiendo lecturas y validando que temperature esté en el rango operacional de -40.0 a 85.0 grados.
- Endpoint GET /api/telemetry/devices/{deviceId}/latest para obtener la última medición registrada de un sensor específico.
- Endpoint GET /api/telemetry/alerts para filtrar lecturas que superen umbrales de alerta crítica.
- Configurar SmallRye OpenAPI para documentación automática de los modelos de sensores.
```

* **Servicio:** `telemetry-service`
* **Base de Datos:** `MYSQL`
* **Mensajería:** `KAFKA`
* **Entidad generada:** `TelemetryReading` (PK: UUID)

---

## Ejemplo 4: Banking Customer KYC & Compliance Service

### Texto para Copiar y Pegar en la UI:
```text
Implementar un microservicio bancario de registro de clientes y validación de cumplimiento KYC (Know Your Customer) llamado customer-service bajo el paquete com.tcs.agentia.customer con PostgreSQL.

Requisitos de Dominio:
- Entidad principal CustomerProfile en la tabla customer_profiles.
- Clave primaria id de tipo UUID.
- Atributos del cliente: documentNumber (tipo String, único y obligatorio, longitud exacta de 8 o 11 dígitos para DNI/RUC), legalName (tipo String, nombre o razón social obligatorio), email (tipo String, @Email obligatorio), kycStatus (tipo String con valores: PENDING_VERIFICATION, APPROVED, REJECTED) y riskLevel (tipo String con valores: LOW, MEDIUM, HIGH).

Reglas de Negocio y Endpoints:
- Endpoint POST /api/customers para dar de alta un nuevo cliente verificando que el documentNumber no esté duplicado (retornar 409 Conflict si ya existe).
- Endpoint GET /api/customers/{id} para consultar el expediente del cliente con sus datos de riesgo y estado KYC.
- Endpoint PATCH /api/customers/{id}/kyc-status para actualizar el dictamen de cumplimiento de riesgos.
- Endpoint GET /api/customers/search?document={documentNumber} para búsqueda rápida de ventanilla.
- Pruebas unitarias y de integración completas con RestAssured y PostgreSQL Testcontainers.
```

* **Servicio:** `customer-service`
* **Base de Datos:** `POSTGRESQL`
* **Mensajería:** `NONE`
* **Entidad generada:** `CustomerProfile` (PK: UUID)

---

## Ejemplo 5: Agile Task Tracker & Sprint Workflow Service

### Texto para Copiar y Pegar en la UI:
```text
Crear un microservicio ágil de gestión de tareas y estados de sprint llamado task-tracker-service bajo el paquete com.tcs.agentia.tasks con base de datos H2 en memoria para pruebas de humo rápidas y desarrollo local.

Requisitos de Dominio:
- Entidad principal ProjectTask en la tabla project_tasks.
- Clave primaria id de tipo Long autoincremental.
- Campos: title (tipo String, obligatorio, longitud entre 5 y 100 caracteres), description (tipo String opcional), assigneeEmail (tipo String con formato de correo @Email), priority (tipo String con valores permitidos: LOW, MEDIUM, HIGH, CRITICAL), status (tipo String con ciclo de vida: TODO, IN_PROGRESS, IN_REVIEW, COMPLETED) y dueDate (tipo LocalDate).

Operaciones REST:
- Endpoint POST /api/tasks para crear una nueva tarea con estado inicial TODO.
- Endpoint GET /api/tasks para listar tareas con filtro opcional por status y assigneeEmail.
- Endpoint PUT /api/tasks/{id}/status para realizar transiciones de estado válidas del flujo de trabajo Kanban.
- Endpoint DELETE /api/tasks/{id} para eliminar tareas canceladas retornando 204 No Content.
- Endpoint GET /api/tasks/{id} para detalle unitario con manejo de 404 Not Found.
- Debe incluir suite de pruebas @QuarkusTest validando todos los códigos HTTP.
```

* **Servicio:** `task-tracker-service`
* **Base de Datos:** `H2`
* **Mensajería:** `NONE`
* **Entidad generada:** `ProjectTask` (PK: Long)

---

## Instrucciones de Uso en AgentIA Studio

1. **Abrir AgentIA Studio** en el navegador (`http://localhost:5173` o el puerto configurado).
2. En la pestaña **0. Definición & Configuración**:
   - Pegue el bloque de texto deseado en el recuadro **"Directiva de Negocio o Comando del PMO"**.
   - Opcionalmente, haga clic en el botón con destellos **"Estructurar con IA (Spec Draft)"** o ejecute paso a paso:
     - `1. Directiva` ➔ Extrae la intención de negocio.
     - `2. Matriz Técnica` ➔ Asigna perfil Quarkus, PostgreSQL/MySQL, Panache y extensiones.
     - `3. Historias BDD` ➔ Genera escenarios Given-When-Then.
     - `4. Panache Models` ➔ Estructura entidades Java con anotaciones `@Entity`, `@Table`, `@Column`.
     - `5. Orquestar` ➔ Lanza la ejecución en el grafo LangGraph hermético.
3. Observe el avance en el **Live Monitor** y en el **Drawer Inferior de Telemetría** con las métricas reales de compilación y sandbox.
