# API Reference

Interactive OpenAPI documentation is served at `/docs`; machine-readable OpenAPI is at `/openapi.json` and is included in the release evidence.

## Operations

- `GET /api/health` — liveness and sanitized runtime inventory; host filesystem paths are not returned.
- `GET /api/readiness` — database reachability/integrity, schema version, directories and secure-configuration status.
- `GET /api/version` — release, phase, environment, build commit and Python requirement.

## Knowledge and security

- `POST /api/documents/upload`
- `GET /api/documents`
- `POST /api/knowledge/search`
- `GET /api/security/incidents`

## Missions and governance

- `POST /api/missions`
- `GET /api/missions`
- `GET /api/missions/{mission_id}`
- `POST /api/missions/{mission_id}/run`
- `POST /api/missions/{mission_id}/control`
- `GET /api/missions/{mission_id}/approvals`
- `POST /api/missions/{mission_id}/approvals/{approval_id}/decide`
- `GET /api/missions/{mission_id}/events`
- `GET /api/missions/{mission_id}/audit`
- `GET /api/missions/{mission_id}/audit/export`
- `GET /api/missions/{mission_id}/stream`

## Tools and integrations

- `GET /api/connectors`
- `POST /api/connectors/{connector_name}/execute`
- `GET /api/tools`
- `POST /api/tools/{tool_name}/call`
- `POST /mcp`

The local demonstration uses `X-Role` and `X-Actor` headers. These prove authorization policy and are not represented as production authentication.
