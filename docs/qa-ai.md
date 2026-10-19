# Guía de IA y Pruebas LLM del Agente de QA (`docs/qa-ai.md`)

Este documento detalla la arquitectura, configuración, garantías de aislamiento y procedimientos de ejecución para las capacidades de **Análisis IA** y la **Suite LLM** en el Agente de Aseguramiento de Calidad de AgentIA.

---

## 1. Matriz de Combinaciones y Tráfico Esperado

El Agente de QA mantiene dos decisiones de ejecución completamente ortogonales e independientes:

| Pruebas LLM (`--suite llm`) | Análisis IA (`--ai-analysis` o `analyze`) | Tráfico de red saliente esperado | Comportamiento |
| :---: | :---: | :---: | :---|
| **Simuladas** (`--llm-mode simulated`, predeterminado) | **Desactivado** (predeterminado) | **CERO llamadas** | 100% offline y determinista. La suite `llm` utiliza dobles controlados de generación y evalúa guards reales de producción. |
| **Simuladas** (`--llm-mode simulated`) | **Activado** (`--ai-analysis` o `analyze`) | **Solo análisis** | Las suites de tests corren offline; al finalizar, se envía un paquete de evidencia mínimo y redactado al proveedor IA configurado. |
| **Reales** (`--llm-mode real`) | **Desactivado** | **Solo pruebas LLM** | La suite `llm` ejerce la frontera LLM real del producto (`ScopedRepairService` / `build_llm_client`). Cero llamadas de análisis. |
| **Reales** (`--llm-mode real`) | **Activado** (`--ai-analysis` o `analyze`) | **Ambas capacidades independientes** | Se ejecutan pruebas LLM reales y análisis IA posterior, con presupuestos, evidencias y credenciales separados. |

> [!IMPORTANT]
> La presencia de credenciales en el entorno **NUNCA** activa el modo real de forma implícita. Ambas capacidades requieren selección explícita por CLI o configuración. Si se especifica `--llm-mode real` sin incluir la suite `llm`, el comando se rechaza con error de configuración (código de salida 2).

---

## 2. Proveedores y Modelos Soportados

El agente implementa clientes HTTPX nativos con verificación TLS estricta y sin bibliotecas pesadas de terceros:

| Proveedor | Adaptador | Variable de Entorno | Endpoint Oficial | Formato de Salida | Modelo de Referencia |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Gemini** | `GeminiProviderAdapter` | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | `responseSchema` (JSON Schema estricto) | `gemini-2.5-flash` |
| **OpenAI** | `OpenAIProviderAdapter` | `OPENAI_API_KEY` | `https://api.openai.com/v1/chat/completions` | `json_schema` estructurado | `gpt-4o-mini` |
| **DeepSeek** | `DeepSeekProviderAdapter` | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/chat/completions` | `json_object` + validación Pydantic | `deepseek-chat` |

*(Nota: `gpt` es un alias sintáctico admitido para `openai`).*

---

## 3. Aislamiento Estricto y Seguridad de Secretos

1. **Lectura exclusiva desde variables de entorno**:
   - Las claves de API solo se leen desde variables de entorno en el momento de uso (`GEMINI_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`).
   - Está prohibido incluir claves en archivos JSON (`qa-config.json`, `result.json`) o en parámetros de línea de comandos. Si se detectan claves como `api_key` o `gemini_api_key` en un JSON de configuración, este se rechaza de inmediato con código de salida 2.
2. **Redacción estricta en artefactos y logs**:
   - Todo diagnóstico, traza y mensaje enviado al paquete de evidencia es procesado por filtros de redacción regex que reemplazan tokens `Bearer <token>` y secuencias sensibles por `[REDACTED]`.
3. **Paquete de evidencia cerrado**:
   - El analizador de IA recibe un paquete estructurado por lista permitida: identificadores de prueba, duraciones, conteos, códigos de estado y diagnósticos acotados.
   - **No se envía código fuente del repositorio, ni archivos `.env`, ni capturas de pantalla, ni trazas de red completas**.
4. **Validación de hipótesis y oráculo anti-alucinaciones**:
   - Las hipótesis generadas por la IA deben citar casos de prueba o suites reales presentes en el run. Toda referencia a elementos inventados es detectada determinísticamente por `validate_hypothesis_references` e invalidada.
   - Las sugerencias de la IA se reportan como hipótesis revisables en `analysis.json` y en el informe HTML; la IA **no tiene permisos para alterar resultados de pruebas, reescribir `result.json` ni ejecutar código en el host**.

---

## 4. Presupuestos y Límites Operacionales

| Parámetro | Límite por Defecto | Comportamiento al Exceder |
| :--- | :---: | :--- |
| **Tamaño del paquete de evidencia** | 32 000 caracteres | Truncado determinista con centinela `[TRUNCATED]` preservando estructura JSON. |
| **Tokens de salida del análisis** | 1 500 tokens | Acotado en la solicitud al proveedor. |
| **Deadline total de análisis** | 120 segundos | `QABudgetExceededError`, entrega marcada como `INCOMPLETE` (código 4). |
| **Timeout por petición HTTP** | 60 segundos (o tiempo restante) | Reintento acotado o fallo tipado `TIMEOUT`. |
| **Máximo de solicitudes por análisis** | 3 llamadas reales | Detiene reintentos inmediatamente. |
| **Máximo de solicitudes por suite `llm`** | 6 llamadas por proveedor | Acota costo y previene bucles de reparación. |

### Política de Códigos de Respuesta HTTP
- **401 Unauthorized / 403 Forbidden**: Falla inmediata sin reintentos (`AUTHENTICATION_ERROR`), exactamente 1 petición efectuada.
- **429 Too Many Requests**: Espera exponencial acotada al deadline restante antes de reintentar.
- **500 / 502 / 503 Server Error**: Reintento acotado al presupuesto máximo de solicitudes.
- **JSON malformado o no conforme**: Se clasifica como `PARSE_ERROR` sin corromper el resultado base de los tests.

---

## 5. Escenario de Reparación `crud-h2` (DELETE 200→204)

La suite `llm` evalúa la capacidad de auto-reparación del producto sobre un defecto real de API REST:

1. **Variante defectuosa**: En `InvoiceResource.java`, el método `DELETE /api/invoice/{id}` devuelve `Response.ok().build()` (HTTP 200).
2. **Control negativo**: El oráculo independiente `OracleInvoiceAcceptanceTest.java` exige `statusCode(204)`. Al evaluarse sobre el código defectuoso, falla con `Expected status code <204> but was <200>`, demostrando que el defecto es detectable.
3. **Petición de reparación**: Se genera un `RepairRequest` tipado dirigido a `src/main/java/com/agentia/qa/invoice/resource/InvoiceResource.java` con presupuesto de 3 intentos.
4. **Frontera LLM**:
   - En modo `simulated`: Se utiliza un generador de Unified Diff determinista.
   - En modo `real`: Se invoca `ScopedRepairService` conectado al cliente LLM del producto (`GeminiLLMClient`, `OpenAICompatibleClient`), pasando el prompt estructurado de reparación.
5. **Evaluación de guardias de producción**:
   - **Guard G1**: Verifica que el parche únicamente modifique la ruta permitida `InvoiceResource.java`.
   - **Guard G3**: Verifica que no se eliminen ni debiliten aserciones en los tests.
   - **Guard G7**: Verifica que no se modifique `pom.xml`.
6. **Aplicación transaccional**: Se aplica el parche al workspace mediante `apply_patch()`.
7. **Control positivo**: Se reevalúa el oráculo independiente, confirmando que ahora devuelve HTTP 204 (`NO_CONTENT`).
8. **Aceptación Java completa** (optativo con `--verify-generated-java`): Si el entorno cuenta con JDK 21, Maven 3.9+ y caché offline Quarkus, ejecuta `mvn test -o -B` para compilar y ejecutar las pruebas JUnit reales sobre H2. Si faltan herramientas, el paso se reporta como `INCOMPLETE` sin simular la compilación.

---

## 6. Ausencia de Credenciales o Cuota

Si se solicita `--llm-mode real` o `--ai-analysis` sin contar con las claves correspondientes en el entorno:
- La ejecución **NUNCA** se aprueba con respuestas falsas o sintéticas disfrazadas de reales.
- El análisis queda en estado `BLOCKED` y la entrega global reporta código de salida **4 (`INCOMPLETE`)**, preservando intacto el resultado determinista de los tests base (código 0 si pasaron, o código 1 si fallaron).

---

## 7. Ejemplos de Uso en CLI

```bash
# 1. Ejecución estándar offline (cero llamadas de red)
python scripts/qa.py run --suite python

# 2. Ejecutar la suite llm en modo simulado (offline, valida guards y reparación)
python scripts/qa.py run --suite llm

# 3. Ejecutar análisis IA sobre la suite python usando Gemini
python scripts/qa.py run --suite python --ai-analysis --ai-provider gemini --ai-model gemini-2.5-flash

# 4. Ejecutar la suite llm en modo real con DeepSeek
python scripts/qa.py run --suite llm --llm-mode real --llm-provider deepseek --llm-model deepseek-chat

# 5. Ejecutar la suite llm en modo real con OpenAI y verificación Maven Java completa
python scripts/qa.py run --suite llm --llm-mode real --llm-provider openai --llm-model gpt-4o-mini --verify-generated-java

# 6. Analizar un resultado existente sin volver a correr tests
python scripts/qa.py analyze --input .agentia-runtime/qa/<trace-id>/result.json --ai-provider gemini
```
