# API and UI Contract

## Blueprint run request

`POST /v1/blueprint/run` continues to accept:

```json
{
  "workspace_dir": "/tmp/agentia-workspace",
  "blueprint": {
    "serviceName": "customer-billing-service",
    "framework": "quarkus",
    "domainModels": [],
    "userStories": [],
    "llm": {
      "provider": "gemini",
      "model": "gemini-2.5-flash"
    }
  },
  "trace_id": "optional-client-trace"
}
```

The `llm` object contains non-secret metadata only. Credentials are never returned in the response.

## Blueprint status

`GET /v1/blueprint/status/{trace_id}` continues to return the existing status shape. It may include selected provider/model metadata, but never credentials.

## UI contract

The run form exposes provider, model, optional endpoint, and masked credential fields. It blocks submission when required values are missing and keeps credentials out of persisted browser state.
