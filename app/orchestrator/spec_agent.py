from __future__ import annotations

import json
import os
import re
from typing import Any

from app.core.llm.client import (
    GeminiLLMClient,
    LLMClient,
    LocalOpenAICompatibleClient,
    OpenAICompatibleClient,
)
from contracts.models import (
    SpecDraftRequest,
    SpecDraftResponse,
    TechnicalMatrix,
    UserStory,
)


class SpecDraftingError(RuntimeError):
    """Raised when the drafting provider cannot produce a valid response."""


SYSTEM_PROMPT = """You are the AgentIA upstream specification drafting agent.
Target stack: Quarkus 3.15, Java 21, Hexagonal Architecture, Panache ORM,
Hibernate Validator, and SmallRye Reactive Messaging.
IDIOMA OBLIGATORIO: TODO el contenido textual y de negocio generado ("business_objective", "title", "given", "when", "then", "acceptance_criteria" en las historias de usuario, y descripciones) DEBE redactarse obligatoriamente en ESPAÑOL.
Convert the business directive into ONLY a JSON object with this EXACT structure:
{
  "service_name": "ejemplo-service",
  "package_name": "com.tcs.ejemplo",
  "business_objective": "Objetivo de negocio claro y conciso en español.",
  "technical_matrix": {
    "database": "POSTGRESQL",
    "messaging": "NONE",
    "scope": "MEDIUM",
    "qps": 1000,
    "transactional_model": "ACID"
  },
  "user_stories": [
    {
      "title": "Título de la historia en español",
      "given": "Dado que (contexto inicial en español)",
      "when": "Cuando (acción disparadora en español)",
      "then": "Entonces (resultado esperado en español)",
      "acceptance_criteria": ["Criterio 1 en español", "Criterio 2 en español"]
    }
  ],
  "domain_models": [
    {
      "name": "EntityName",
      "table_name": "entity_names",
      "fields": [
        {
          "name": "id",
          "type": "Long",
          "nullable": false,
          "constraints": ["@NotNull"]
        }
      ]
    }
  ]
}
Notes on valid values:
- IDIOMA: Absolutamente todas las historias BDD ("given", "when", "then", "acceptance_criteria") y el objetivo deben estar redactadas en ESPAÑOL.
- technical_matrix.database: POSTGRESQL, MYSQL, H2, or NONE
- technical_matrix.messaging: KAFKA, RABBITMQ, or NONE (use KAFKA only if async/event-driven events are requested)
- technical_matrix.transactional_model: ACID or EVENTUAL
- field constraints must ALWAYS be a list of strings (e.g. ["@NotNull", "@Positive"])
- every domain_model MUST have both "name" and "table_name"
- every user_story MUST have "title", "given", "when", "then" en español
Return ONLY raw JSON, with no markdown fences, no backticks, and no conversational text."""


class SpecDraftingAgent:
    def __init__(self, llm_client: LLMClient | Any | None = None) -> None:
        self.llm_client = llm_client

    async def draft(self, request: SpecDraftRequest) -> SpecDraftResponse:
        try:
            client = self._client_for(request)
            prompt = self._prompt(request)
            first = await client.generate(prompt)
        except Exception:  # noqa: BLE001
            return self._fallback(request)
        try:
            return self._parse(first.content, request)
        except (ValueError, TypeError, json.JSONDecodeError):
            correction = (
                f"{prompt}\n\nYour previous response was invalid. Return only a "
                "schema-valid JSON object matching the exact structure requested. Previous response:\n"
                f"{first.content[:12000]}"
            )
            second = await client.generate(correction)
            try:
                return self._parse(second.content, request)
            except (ValueError, TypeError, json.JSONDecodeError):
                return self._fallback(request)

    def _client_for(self, request: SpecDraftRequest) -> Any:
        if self.llm_client is not None:
            return self.llm_client

        config = request.llm_config
        if config is None:
            local_ep = os.getenv("LOCAL_LLM_ENDPOINT") or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:8080"
            return LocalOpenAICompatibleClient(
                endpoint=local_ep,
                model_name=os.getenv("LLM_MODEL", "qwen2.5-coder:7b"),
            )

        if config.provider == "gemini":
            return GeminiLLMClient(
                api_key=config.api_key,
                model_name=config.model,
            )

        if config.provider == "local":
            return LocalOpenAICompatibleClient(
                endpoint=config.endpoint or os.getenv("LOCAL_LLM_ENDPOINT") or "http://127.0.0.1:8080",
                model_name=config.model,
                api_key=config.api_key,
            )

        if config.provider == "openai":
            return OpenAICompatibleClient(
                endpoint=config.endpoint or os.getenv("OPENAI_API_BASE", "https://genailab.tcs.in/v1"),
                model_name=config.model,
                api_key=config.api_key or os.getenv("OPENAI_API_KEY"),
            )

        raise SpecDraftingError(f"Unsupported LLM provider: {config.provider}")

    def _prompt(self, request: SpecDraftRequest) -> str:
        base = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Directiva de negocio del usuario: {request.directive}\n"
            f"Nombre de microservicio solicitado: {request.service_name or 'inferir de forma segura'}\n"
            f"Paquete Java solicitado: {request.package_name or 'inferir de forma segura'}"
        )
        if request.refinement_instructions:
            base += f"\n\nINSTRUCCIONES DE REFINAMIENTO DEL USUARIO (EN ESPAÑOL):\n{request.refinement_instructions}"
        if request.current_context:
            try:
                ctx_json = json.dumps(request.current_context, indent=2, ensure_ascii=False)
                base += f"\n\nCONTEXTO ACTUAL DE ESPECIFICACIÓN A REFINAR / ACTUALIZAR:\n{ctx_json}"
            except Exception:
                pass

        base += "\n\nRecuerde: Genere todo el contenido descriptivo y de historias de usuario en ESPAÑOL."
        return base

    @classmethod
    def _normalize_data(cls, data: dict[str, Any], request: SpecDraftRequest) -> dict[str, Any]:
        """Tolerantly normalize LLM output to conform to SpecDraftResponse schema."""
        norm = dict(data)

        if not norm.get("service_name") or not isinstance(norm["service_name"], str):
            norm["service_name"] = request.service_name or _safe_name(request.directive[:30])
        else:
            norm["service_name"] = _safe_name(norm["service_name"])

        if not norm.get("package_name") or not isinstance(norm["package_name"], str):
            norm["package_name"] = request.package_name or "com.tcs." + norm["service_name"].replace("-", "")

        if not norm.get("business_objective") or not isinstance(norm["business_objective"], str):
            norm["business_objective"] = request.directive.strip()

        raw_tm = norm.get("technical_matrix")
        tm: dict[str, Any] = {}
        if isinstance(raw_tm, dict):
            db = str(raw_tm.get("database", "")).upper()
            if db not in {"POSTGRESQL", "MYSQL", "H2", "NONE"}:
                db_candidate = "MYSQL" if "mysql" in request.directive.lower() else "POSTGRESQL"
                db = db_candidate
            tm["database"] = db

            msg = str(raw_tm.get("messaging", "")).upper()
            if msg not in {"KAFKA", "RABBITMQ", "NONE"}:
                recommendations = raw_tm.get("recommendations", {})
                if isinstance(recommendations, dict) and recommendations.get("kafka") is True or any(w in request.directive.lower() for w in ("kafka", "topic", "stream", "evento")):
                    msg = "KAFKA"
                else:
                    msg = "NONE"
            tm["messaging"] = msg

            scope = str(raw_tm.get("scope", "MEDIUM")).upper()
            tm["scope"] = scope if scope in {"LOW", "MEDIUM", "HIGH"} else "MEDIUM"

            qps_val = raw_tm.get("qps", 1000)
            try:
                tm["qps"] = max(0, int(qps_val))
            except (ValueError, TypeError):
                tm["qps"] = 1000

            tx = str(raw_tm.get("transactional_model", "ACID")).upper()
            tm["transactional_model"] = tx if tx in {"ACID", "EVENTUAL"} else "ACID"
        else:
            tm = {
                "database": "MYSQL" if "mysql" in request.directive.lower() else "POSTGRESQL",
                "messaging": "KAFKA" if "kafka" in request.directive.lower() else "NONE",
                "scope": "MEDIUM",
                "qps": 1000,
                "transactional_model": "ACID",
            }
        norm["technical_matrix"] = tm

        raw_stories = norm.get("user_stories")
        clean_stories = []
        if isinstance(raw_stories, list):
            for i, story in enumerate(raw_stories):
                if not isinstance(story, dict):
                    continue
                given = str(story.get("given", "Contexto inicial disponible")).strip() or "Contexto inicial"
                when = str(story.get("when", "Se ejecuta la operacion")).strip() or "Accion realizada"
                then = str(story.get("then", "Se produce el resultado esperado")).strip() or "Resultado esperado"
                title = str(story.get("title", "")).strip()
                if not title:
                    title = f"Historia {i + 1}: {when[:50]}"

                ac = story.get("acceptance_criteria", [])
                if isinstance(ac, str):
                    ac = [ac]
                elif not isinstance(ac, list) or not ac:
                    ac = [f"Dado {given}, cuando {when}, entonces {then}"]
                else:
                    ac = [str(item).strip() for item in ac if str(item).strip()]

                clean_stories.append({
                    "title": title,
                    "given": given,
                    "when": when,
                    "then": then,
                    "acceptance_criteria": ac,
                })
        norm["user_stories"] = clean_stories

        raw_models = norm.get("domain_models")
        clean_models = []
        if isinstance(raw_models, list):
            for model in raw_models:
                if not isinstance(model, dict):
                    continue
                name = str(model.get("name", "")).strip()
                if not name:
                    continue

                table_name = str(model.get("table_name", "")).strip()
                if not table_name:
                    table_name = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower() + "s"

                raw_fields = model.get("fields", [])
                clean_fields = []
                if isinstance(raw_fields, list):
                    for field in raw_fields:
                        if not isinstance(field, dict):
                            continue
                        fname = str(field.get("name", "")).strip()
                        if not fname:
                            continue
                        ftype = str(field.get("type", "String")).strip() or "String"
                        nullable = bool(field.get("nullable", True))

                        fconstraints = field.get("constraints", [])
                        if isinstance(fconstraints, str):
                            fconstraints = [c.strip() for c in fconstraints.split(",") if c.strip()]
                        elif isinstance(fconstraints, list):
                            fconstraints = [str(c).strip() for c in fconstraints if str(c).strip()]
                        else:
                            fconstraints = []

                        clean_fields.append({
                            "name": fname,
                            "type": ftype,
                            "nullable": nullable,
                            "constraints": fconstraints,
                        })

                clean_models.append({
                    "name": name,
                    "table_name": table_name,
                    "fields": clean_fields,
                })
        norm["domain_models"] = clean_models

        return norm

    @classmethod
    def _parse(cls, raw: str, request: SpecDraftRequest) -> SpecDraftResponse:
        content = raw.strip()
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, flags=re.DOTALL | re.IGNORECASE)
        if fence_match:
            content = fence_match.group(1).strip()
        elif content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE).strip()
        elif not content.startswith("{"):
            brace_match = re.search(r"(\{.*\})", content, flags=re.DOTALL)
            if brace_match:
                content = brace_match.group(1).strip()
        data = json.loads(content)
        if not isinstance(data, dict):
            raise TypeError("draft response must be a JSON object")
        normalized = cls._normalize_data(data, request)
        return SpecDraftResponse.model_validate(normalized)

    @staticmethod
    def _fallback(request: SpecDraftRequest) -> SpecDraftResponse:
        from typing import Literal

        from contracts.models import DomainModel, FieldSpec

        directive_lower = request.directive.lower()
        messaging_type: Literal["KAFKA", "RABBITMQ", "NONE"] = (
            "KAFKA"
            if any(w in directive_lower for w in ("kafka", "topic", "stream", "evento"))
            else "NONE"
        )
        db_type: Literal["POSTGRESQL", "MYSQL", "H2", "NONE"] = (
            "MYSQL" if "mysql" in directive_lower else "POSTGRESQL"
        )

        if "wallet" in directive_lower or "billetera" in directive_lower:
            service_name = request.service_name or "customer-wallet-service"
            package_name = request.package_name or "com.tcs.wallet"
            models = [
                DomainModel(
                    name="DigitalWallet",
                    table_name="digital_wallets",
                    fields=[
                        FieldSpec(name="id", type="UUID", nullable=False, constraints=["@NotNull"]),
                        FieldSpec(name="ownerDocument", type="String", nullable=False, constraints=["@NotBlank"]),
                        FieldSpec(name="balance", type="BigDecimal", nullable=False, constraints=["@PositiveOrZero"]),
                        FieldSpec(name="currency", type="String", nullable=False, constraints=["@NotBlank"]),
                        FieldSpec(name="status", type="String", nullable=False, constraints=["@NotBlank"]),
                    ],
                ),
                DomainModel(
                    name="WalletLedgerEntry",
                    table_name="wallet_ledger_entries",
                    fields=[
                        FieldSpec(name="id", type="UUID", nullable=False, constraints=["@NotNull"]),
                        FieldSpec(name="walletId", type="UUID", nullable=False, constraints=["@NotNull"]),
                        FieldSpec(name="entryType", type="String", nullable=False, constraints=["@NotBlank"]),
                        FieldSpec(name="amount", type="BigDecimal", nullable=False, constraints=["@Positive"]),
                        FieldSpec(name="timestamp", type="Instant", nullable=False, constraints=["@NotNull"]),
                    ],
                ),
            ]
            stories = [
                UserStory(
                    title="Recarga y balance de billetera digital",
                    given="Una billetera activa con identificador y documento válido",
                    when="Se efectúa una operación de recarga en el endpoint de balance",
                    then="Se incrementa el saldo y se persiste con aislamiento transaccional",
                    acceptance_criteria=["Monto estrictamente positivo", "Actualización de timestamp"],
                ),
                UserStory(
                    title="Transferencia entre billeteras con control de límite",
                    given="Billeteras origen y destino activas con saldo disponible",
                    when="Se procesa una transferencia inmediata",
                    then="Se actualizan ambos balances atómicamente y se emite evento de confirmación",
                    acceptance_criteria=["Transacción atómica ACID", "Emisión de evento Kafka"],
                ),
            ]
            return SpecDraftResponse(
                service_name=service_name,
                package_name=package_name,
                business_objective=request.directive.strip(),
                technical_matrix=TechnicalMatrix(
                    database=db_type,
                    messaging=messaging_type if messaging_type != "NONE" else "KAFKA",
                    scope="MEDIUM",
                    qps=1000,
                    transactional_model="ACID",
                ),
                user_stories=stories,
                domain_models=models,
            )

        if any(w in directive_lower for w in ("pago", "payment", "transfer", "soles", "cce")):
            service_name = request.service_name or "payment-transfers-service"
            package_name = request.package_name or "com.tcs.payments"
            models = [
                DomainModel(
                    name="PaymentTransfer",
                    table_name="payment_transfers",
                    fields=[
                        FieldSpec(name="id", type="UUID", nullable=False, constraints=["@NotNull"]),
                        FieldSpec(name="originAccount", type="String", nullable=False, constraints=["@NotBlank"]),
                        FieldSpec(name="destinationAccount", type="String", nullable=False, constraints=["@NotBlank"]),
                        FieldSpec(name="amount", type="BigDecimal", nullable=False, constraints=["@NotNull", "@Positive"]),
                        FieldSpec(name="currency", type="String", nullable=False, constraints=["@NotBlank"]),
                        FieldSpec(name="status", type="String", nullable=False, constraints=["@NotBlank"]),
                        FieldSpec(name="createdAt", type="Instant", nullable=False, constraints=["@NotNull"]),
                    ],
                ),
                DomainModel(
                    name="DailyLimitAccumulator",
                    table_name="daily_limit_accumulators",
                    fields=[
                        FieldSpec(name="id", type="UUID", nullable=False, constraints=["@NotNull"]),
                        FieldSpec(name="customerId", type="String", nullable=False, constraints=["@NotBlank"]),
                        FieldSpec(name="totalAmountPen", type="BigDecimal", nullable=False, constraints=["@NotNull"]),
                        FieldSpec(name="maxDailyLimit", type="BigDecimal", nullable=False, constraints=["@Positive"]),
                        FieldSpec(name="lastUpdated", type="Instant", nullable=False, constraints=["@NotNull"]),
                    ],
                ),
            ]
            stories = [
                UserStory(
                    title="Procesar transferencia con validación de límite diario en soles",
                    given="El cliente posee saldo disponible y no excede el límite operativo diario",
                    when="Se envía solicitud de transferencia con cuenta origen y destino",
                    then="Se debita la cuenta origen, se acredita destino y se emite evento de confirmación",
                    acceptance_criteria=["Monto estrictamente positivo", "Bloqueo transaccional ACID", "Evento Kafka"],
                ),
                UserStory(
                    title="Rollback atómico ante fondos insuficientes o límite superado",
                    given="El saldo es insuficiente o supera el límite diario configurado",
                    when="Se intenta procesar la transacción",
                    then="Se rechaza con error de negocio y se ejecuta rollback atómico",
                    acceptance_criteria=["Cero mutación de saldo", "Registro de auditoría"],
                ),
            ]
            return SpecDraftResponse(
                service_name=service_name,
                package_name=package_name,
                business_objective=request.directive.strip(),
                technical_matrix=TechnicalMatrix(
                    database=db_type,
                    messaging=messaging_type,
                    scope="MEDIUM",
                    qps=1000,
                    transactional_model="ACID",
                ),
                user_stories=stories,
                domain_models=models,
            )

        service_name = request.service_name or "order-fulfillment-service"
        package_name = request.package_name or f"com.example.{_safe_name(service_name)}"
        entity_name = _safe_entity_name(service_name)
        models = [
            DomainModel(
                name=entity_name,
                table_name=f"{_safe_name(service_name).replace('-service', '').replace('-', '_')}_records",
                fields=[
                    FieldSpec(name="id", type="Long", nullable=False, constraints=["@NotNull"]),
                    FieldSpec(name="referenceCode", type="String", nullable=False, constraints=["@NotBlank"]),
                    FieldSpec(name="totalAmount", type="BigDecimal", nullable=False, constraints=["@Positive"]),
                    FieldSpec(name="status", type="String", nullable=False, constraints=["@NotBlank"]),
                    FieldSpec(name="createdAt", type="Instant", nullable=False, constraints=["@NotNull"]),
                ],
            )
        ]
        stories = [
            UserStory(
                title=f"Procesamiento transaccional de {service_name}",
                given="Entorno Quarkus con persistencia Panache configurada",
                when="Se procesa una instrucción conforme a la directiva de negocio",
                then="Se aplican las reglas y se persiste el estado transaccional",
                acceptance_criteria=[request.directive.strip()],
            ),
            UserStory(
                title="Consulta y trazabilidad por identificador",
                given="El registro se encuentra persistido en base de datos",
                when="Se consulta por su identificador único",
                then="Se retorna el estado actual con serialización Jackson",
                acceptance_criteria=["Respuesta JSON con código HTTP 200 OK"],
            ),
        ]
        return SpecDraftResponse(
            service_name=service_name,
            package_name=package_name,
            business_objective=request.directive.strip(),
            technical_matrix=TechnicalMatrix(
                database=db_type,
                messaging=messaging_type,
                scope="MEDIUM",
                qps=1000,
                transactional_model="ACID",
            ),
            user_stories=stories,
            domain_models=models,
        )


def _safe_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "service"


def _safe_entity_name(service_name: str) -> str:
    cleaned = service_name.replace("-service", "").replace("service", "")
    parts = [p.capitalize() for p in re.split(r"[-_]+", cleaned) if p]
    return "".join(parts) or "EntityRecord"