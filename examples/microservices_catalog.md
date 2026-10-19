# Catálogo de Ejemplos de Microservicios: AgentIA v2
**Uso:** Copie y pegue estos ejemplos directamente en la interfaz de **AgentIA Studio** o pruébelos mediante el backend API para observar la generación, verificación y monitoreo en tiempo real.

> 💡 **¿Buscas solo el texto en lenguaje natural para la UI?**  
> Hemos preparado el archivo dedicado [`examples/text_description_inputs.md`](file:///home/gjanampa/Projects/AI_AGENTS/agentIA_v2/examples/text_description_inputs.md) con las directivas listas para copiar y pegar en 1 clic en el campo **"Directiva de Negocio o Comando del PMO"**. Cada ejemplo a continuación también incluye su bloque `💬 Directiva de Negocio`.

---

## Índice de Ejemplos
1. [Ejemplo 1: Order Service (PostgreSQL + Kafka + UUID + Bean Validation)](#ejemplo-1-order-service)
2. [Ejemplo 2: Payment Escrow Service (PostgreSQL + ACID + Clave Long)](#ejemplo-2-payment-escrow-service)
3. [Ejemplo 3: Telemetry Ingestion Service (MySQL + Kafka Streams + IoT)](#ejemplo-3-telemetry-ingestion-service)
4. [Ejemplo 4: Customer Profile Service (PostgreSQL + UUID + Restricción Unicidad)](#ejemplo-4-customer-profile-service)
5. [Ejemplo 5: Task Tracker Service (H2 En Memoria - Prueba Rápida de Humo)](#ejemplo-5-task-tracker-service)

---

## Ejemplo 1: Order Service
> **Perfil:** Comercio Electrónico, órdenes de compra transaccionales y publicación a tópicos Kafka.  
> **Stack:** Quarkus 3.15 LTS, PostgreSQL, SmallRye Reactive Messaging Kafka, Clave Primaria UUID.

### 💬 Directiva de Negocio (Text Description Input para la UI)
> Copie y pegue este texto directamente en el campo **"Directiva de Negocio o Comando del PMO"** (Tab 0) y presione *"Estructurar con IA"* o ejecute el paso a paso:

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

### Instrucciones para la UI (AgentIA Studio)
- **Pestaña "1. Definición & Configuración":**
  - **Nombre del Microservicio:** `order-service`
  - **Paquete Base:** `com.tcs.agentia.order`
  - **Base de Datos:** `POSTGRESQL`
  - **Sistema de Mensajería:** `KAFKA`
  - **Descripción:** *Microservicio para registro y consulta de órdenes de compra con persistencia en PostgreSQL y publicación de eventos transaccionales en Apache Kafka.*
- **Pestaña "2. Requisitos & Historias BDD":**
  - Copiar la historia de usuario `US-001` y `US-002`.
- **Pestaña "3. Arquitectura & Modelos":**
  - Entidad: `PurchaseOrder` | Tabla: `purchase_orders`
  - Campos: `id (UUID, PK)`, `customerEmail (String, @Email, @NotNull)`, `totalAmount (BigDecimal, @Positive, @NotNull)`, `status (String)`, `createdAt (Instant)`.

### Payload JSON Completo (Listo para importar o ejecutar vía API)
```json
{
  "serviceName": "order-service",
  "name": "order-service",
  "packageName": "com.tcs.agentia.order",
  "framework": "quarkus-3",
  "frameworkVersion": "3.15.1",
  "description": "Microservicio de gestión de órdenes de compra con persistencia en PostgreSQL y eventos Kafka.",
  "parameters": {
    "database": "POSTGRESQL",
    "messaging": "KAFKA",
    "requirementsSize": "MEDIUM",
    "workspaceDir": "/tmp/agentia-workspace/order-service",
    "testMode": "full"
  },
  "userStories": [
    {
      "id": "US-001",
      "title": "Creación y persistencia de orden de compra",
      "role": "Cliente del Comercio Electrónico",
      "feature": "Registrar una nueva orden con validación de montos e ítems",
      "benefit": "Asegurar el procesamiento financiero y disparar el aprovisionamiento",
      "scenarios": [
        {
          "title": "Creación exitosa con datos válidos",
          "given": "El cliente provee un email válido y un total superior a cero",
          "when": "Se envía POST /api/orders con el payload de la orden",
          "then": "Se retorna 201 Created con cabecera Location y el identificador UUID asignado"
        },
        {
          "title": "Rechazo por monto inválido",
          "given": "El payload contiene totalAmount negativo o cero",
          "when": "Se invoca POST /api/orders",
          "then": "Se retorna 400 Bad Request por violación de validación Jakarta"
        }
      ],
      "acceptanceCriteria": [
        "El ID debe generarse de forma automática como UUID sin ser sobreescrito por el cliente",
        "El estado inicial debe ser PENDING_PAYMENT",
        "La fecha createdAt debe ser asignada automáticamente al instante de recepción"
      ]
    },
    {
      "id": "US-002",
      "title": "Consulta y rastreo de orden por identificador",
      "role": "Sistema de Seguimiento / Cliente",
      "feature": "Obtener el detalle y estado actual de una orden existente",
      "benefit": "Monitoreo en tiempo real del ciclo de entrega",
      "scenarios": [
        {
          "title": "Consulta de orden existente",
          "given": "Existe una orden persistida con ID conocido",
          "when": "Se realiza GET /api/orders/{id}",
          "then": "Se retorna 200 OK con la representación JSON completa"
        },
        {
          "title": "Consulta de orden inexistente",
          "given": "No existe registro para el ID solicitado",
          "when": "Se realiza GET /api/orders/999999",
          "then": "Se retorna 404 Not Found"
        }
      ]
    }
  ],
  "entities": [
    {
      "name": "PurchaseOrder",
      "tableName": "purchase_orders",
      "description": "Entidad principal de orden de compra agregada",
      "fields": [
        { "name": "id", "type": "UUID", "primaryKey": true, "nullable": false },
        { "name": "customerEmail", "type": "String", "nullable": false, "validationRules": ["@Email", "@NotNull"] },
        { "name": "totalAmount", "type": "BigDecimal", "nullable": false, "validationRules": ["@Positive", "@NotNull"] },
        { "name": "status", "type": "String", "nullable": false },
        { "name": "createdAt", "type": "Instant", "nullable": false }
      ]
    }
  ]
}
```

---

## Ejemplo 2: Payment Escrow Service
> **Perfil:** Pagos en custodia, retención de fondos y confirmación bilateral.  
> **Stack:** Quarkus 3.15 LTS, PostgreSQL, Hibernate Panache, Transacciones ACID `@Transactional`.

### 💬 Directiva de Negocio (Text Description Input para la UI)
> Copie y pegue este texto directamente en el campo **"Directiva de Negocio o Comando del PMO"** (Tab 0):

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

### Instrucciones para la UI
- **Pestaña "1. Definición & Configuración":**
  - **Nombre:** `payment-escrow-service`
  - **Paquete:** `com.tcs.agentia.escrow`
  - **Base de Datos:** `POSTGRESQL`
  - **Mensajería:** `NONE`
- **Pestaña "3. Arquitectura & Modelos":**
  - Entidad: `EscrowContract` | Tabla: `escrow_contracts`
  - Campos: `id (Long, PK)`, `contractCode (String, @NotBlank, Unique)`, `heldAmount (BigDecimal, @Positive)`, `buyerAccount (String)`, `sellerAccount (String)`, `status (String)`, `createdAt (Instant)`.

### Payload JSON Completo
```json
{
  "serviceName": "payment-escrow-service",
  "name": "payment-escrow-service",
  "packageName": "com.tcs.agentia.escrow",
  "framework": "quarkus-3",
  "frameworkVersion": "3.15.1",
  "description": "Microservicio financiero de retención y liquidación de pagos en custodia (Escrow).",
  "parameters": {
    "database": "POSTGRESQL",
    "messaging": "NONE",
    "requirementsSize": "SMALL",
    "workspaceDir": "/tmp/agentia-workspace/payment-escrow-service",
    "testMode": "full"
  },
  "userStories": [
    {
      "id": "US-ESC-01",
      "title": "Retención de fondos en custodia",
      "role": "Operador de Pagos",
      "feature": "Bloquear fondos de una transacción hasta la confirmación de entrega",
      "benefit": "Mitigar fraude bilateral entre comprador y vendedor",
      "scenarios": [
        {
          "title": "Custodia exitosa",
          "given": "Monto positivo y cuentas válidas de emisor y receptor",
          "when": "POST /api/escrowcontract con estado HELD",
          "then": "Se persiste el contrato en PostgreSQL retornando 201 Created"
        }
      ]
    }
  ],
  "entities": [
    {
      "name": "EscrowContract",
      "tableName": "escrow_contracts",
      "description": "Contrato de custodia financiera",
      "fields": [
        { "name": "id", "type": "Long", "primaryKey": true, "nullable": false },
        { "name": "contractCode", "type": "String", "nullable": false, "unique": true, "validationRules": ["@NotBlank"] },
        { "name": "heldAmount", "type": "BigDecimal", "nullable": false, "validationRules": ["@Positive"] },
        { "name": "buyerAccount", "type": "String", "nullable": false },
        { "name": "sellerAccount", "type": "String", "nullable": false },
        { "name": "status", "type": "String", "nullable": false },
        { "name": "createdAt", "type": "Instant", "nullable": false }
      ]
    }
  ]
}
```

---

## Ejemplo 3: Telemetry Ingestion Service
> **Perfil:** IoT industrial, telemetría de alta frecuencia y streaming reactivo.  
> **Stack:** Quarkus 3.15 LTS, MySQL, Apache Kafka, SmallRye Reactive Messaging.

### 💬 Directiva de Negocio (Text Description Input para la UI)
> Copie y pegue este texto directamente en el campo **"Directiva de Negocio o Comando del PMO"** (Tab 0):

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

### Instrucciones para la UI
- **Pestaña "1. Definición & Configuración":**
  - **Nombre:** `telemetry-ingestion-service`
  - **Paquete:** `com.tcs.agentia.iot`
  - **Base de Datos:** `MYSQL`
  - **Mensajería:** `KAFKA`
- **Pestaña "3. Arquitectura & Modelos":**
  - Entidad: `DeviceSensor` | Tabla: `device_sensors`
  - Campos: `id (Long, PK)`, `deviceId (String, @NotBlank)`, `metricType (String)`, `metricValue (Double)`, `recordedAt (Instant)`.

### Payload JSON Completo
```json
{
  "serviceName": "telemetry-ingestion-service",
  "name": "telemetry-ingestion-service",
  "packageName": "com.tcs.agentia.iot",
  "framework": "quarkus-3",
  "frameworkVersion": "3.15.1",
  "description": "Microservicio de ingesta de telemetría de sensores IoT con MySQL y streaming Kafka.",
  "parameters": {
    "database": "MYSQL",
    "messaging": "KAFKA",
    "requirementsSize": "MEDIUM",
    "workspaceDir": "/tmp/agentia-workspace/telemetry-ingestion-service",
    "testMode": "full"
  },
  "userStories": [
    {
      "id": "US-IOT-01",
      "title": "Registro de telemetría de dispositivo",
      "role": "Gateway de Sensores IoT",
      "feature": "Ingesta masiva de lecturas de temperatura y presión",
      "benefit": "Detección temprana de anomalías en equipamiento industrial",
      "scenarios": [
        {
          "title": "Recepción de telemetría normal",
          "given": "Identificador de dispositivo y métricas válidas",
          "when": "POST /api/devicesensor",
          "then": "Retorna 201 Created y emite evento al canal de streaming"
        }
      ]
    }
  ],
  "entities": [
    {
      "name": "DeviceSensor",
      "tableName": "device_sensors",
      "description": "Lecturas cronológicas de telemetría industrial",
      "fields": [
        { "name": "id", "type": "Long", "primaryKey": true, "nullable": false },
        { "name": "deviceId", "type": "String", "nullable": false, "validationRules": ["@NotBlank"] },
        { "name": "metricType", "type": "String", "nullable": false },
        { "name": "metricValue", "type": "Double", "nullable": false },
        { "name": "recordedAt", "type": "Instant", "nullable": false }
      ]
    }
  ]
}
```

---

## Ejemplo 4: Customer Profile Service
> **Perfil:** Maestro de clientes, verificación de unicidad de email y claves naturales UUID.  
> **Stack:** Quarkus 3.15 LTS, PostgreSQL, PanacheRepositoryBase<CustomerProfile, UUID>.

### 💬 Directiva de Negocio (Text Description Input para la UI)
> Copie y pegue este texto directamente en el campo **"Directiva de Negocio o Comando del PMO"** (Tab 0):

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

### Instrucciones para la UI
- **Pestaña "1. Definición & Configuración":**
  - **Nombre:** `customer-profile-service`
  - **Paquete:** `com.tcs.agentia.customer`
  - **Base de Datos:** `POSTGRESQL`
  - **Mensajería:** `NONE`
- **Pestaña "3. Arquitectura & Modelos":**
  - Entidad: `CustomerProfile` | Tabla: `customer_profiles`
  - Campos: `id (UUID, PK)`, `fullName (String, @NotBlank)`, `email (String, @Email, Unique)`, `phoneNumber (String, Nullable)`, `tier (String)`, `active (Boolean)`.

### Payload JSON Completo
```json
{
  "serviceName": "customer-profile-service",
  "name": "customer-profile-service",
  "packageName": "com.tcs.agentia.customer",
  "framework": "quarkus-3",
  "frameworkVersion": "3.15.1",
  "description": "Microservicio de gestión de perfiles de clientes con UUID y unicidad de email.",
  "parameters": {
    "database": "POSTGRESQL",
    "messaging": "NONE",
    "requirementsSize": "SMALL",
    "workspaceDir": "/tmp/agentia-workspace/customer-profile-service",
    "testMode": "full"
  },
  "userStories": [
    {
      "id": "US-CUST-01",
      "title": "Registro de perfil de cliente",
      "role": "Usuario / Portal Web",
      "feature": "Alta de usuario con verificación de correo y teléfono",
      "benefit": "Centralización de identidad de clientes",
      "scenarios": [
        {
          "title": "Alta exitosa de cliente",
          "given": "Email corporativo no registrado previamente",
          "when": "POST /api/customerprofile",
          "then": "Retorna 201 Created con entidad registrada"
        }
      ]
    }
  ],
  "entities": [
    {
      "name": "CustomerProfile",
      "tableName": "customer_profiles",
      "description": "Ficha maestra de datos del cliente",
      "fields": [
        { "name": "id", "type": "UUID", "primaryKey": true, "nullable": false },
        { "name": "fullName", "type": "String", "nullable": false, "validationRules": ["@NotBlank"] },
        { "name": "email", "type": "String", "nullable": false, "unique": true, "validationRules": ["@Email", "@NotNull"] },
        { "name": "phoneNumber", "type": "String", "nullable": true },
        { "name": "tier", "type": "String", "nullable": false },
        { "name": "active", "type": "Boolean", "nullable": false }
      ]
    }
  ]
}
```

---

## Ejemplo 5: Task Tracker Service (Prueba Inmediata de Humo)
> **Perfil:** Gestión de sprints y tareas ágiles con **base de datos H2 en memoria**.  
> **Ventaja:** Cero dependencias externas. Se compila y ejecuta al instante sin necesidad de levantar contenedores de bases de datos.

### 💬 Directiva de Negocio (Text Description Input para la UI)
> Copie y pegue este texto directamente en el campo **"Directiva de Negocio o Comando del PMO"** (Tab 0):

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

### Instrucciones para la UI
- **Pestaña "1. Definición & Configuración":**
  - **Nombre:** `task-tracker-service`
  - **Paquete:** `com.tcs.agentia.tracker`
  - **Base de Datos:** `H2`
  - **Mensajería:** `NONE`
- **Pestaña "3. Arquitectura & Modelos":**
  - Entidad: `AgileTask` | Tabla: `agile_tasks`
  - Campos: `id (Long, PK)`, `title (String, @NotBlank)`, `assignee (String)`, `storyPoints (Integer, @Min(1))`, `status (String)`.

### Payload JSON Completo
```json
{
  "serviceName": "task-tracker-service",
  "name": "task-tracker-service",
  "packageName": "com.tcs.agentia.tracker",
  "framework": "quarkus-3",
  "frameworkVersion": "3.15.1",
  "description": "Microservicio ágil de seguimiento de tareas con base de datos H2 en memoria.",
  "parameters": {
    "database": "H2",
    "messaging": "NONE",
    "requirementsSize": "SMALL",
    "workspaceDir": "/tmp/agentia-workspace/task-tracker-service",
    "testMode": "full"
  },
  "userStories": [
    {
      "id": "US-TSK-01",
      "title": "Ciclo de vida de tarea ágil",
      "role": "Desarrollador / Scrum Master",
      "feature": "Crear, consultar, actualizar y eliminar tareas de un sprint",
      "benefit": "Control de entregables del equipo sin configuración de base de datos externa",
      "scenarios": [
        {
          "title": "Creación y listado de tarea",
          "given": "Título y estado de tarea",
          "when": "POST /api/agiletask y posterior GET /api/agiletask",
          "then": "Retorna 201 Created y 200 OK con la lista conteniendo la nueva tarea"
        }
      ]
    }
  ],
  "entities": [
    {
      "name": "AgileTask",
      "tableName": "agile_tasks",
      "description": "Elemento de trabajo del backlog",
      "fields": [
        { "name": "id", "type": "Long", "primaryKey": true, "nullable": false },
        { "name": "title", "type": "String", "nullable": false, "validationRules": ["@NotBlank"] },
        { "name": "assignee", "type": "String", "nullable": true },
        { "name": "storyPoints", "type": "Integer", "nullable": false, "validationRules": ["@Min(1)"] },
        { "name": "status", "type": "String", "nullable": false }
      ]
    }
  ]
}
```

---

## Cómo Probar vía Terminal con cURL

Para disparar la validación y generación directa de cualquiera de estos ejemplos:

```bash
# Validar el esquema en AgentIA v2
curl -X POST http://127.0.0.1:8000/v1/blueprint/validate \
  -H "Content-Type: application/json" \
  -H "x-api-key: development-secret-key" \
  -d @<(python3 -c "import json; d=json.load(open('examples/microservices_catalog.json')); print(json.dumps({'workspace_dir': '/tmp/agentia-workspace/task-tracker-service', 'blueprint': d['examples'][4]}))")

# Disparar la generación, compilación hermética y verificación en vivo
curl -X POST http://127.0.0.1:8000/v1/blueprint/run \
  -H "Content-Type: application/json" \
  -H "x-api-key: development-secret-key" \
  -d @<(python3 -c "import json; d=json.load(open('examples/microservices_catalog.json')); print(json.dumps({'workspace_dir': '/tmp/agentia-workspace/task-tracker-service', 'blueprint': d['examples'][4]}))")
```

