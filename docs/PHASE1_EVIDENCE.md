# Historical Phase 1 Requirement-to-Evidence Matrix

> Historical baseline: Phase 1 used nine agents. The final Phase 3 release uses eleven governed agents and five registered tools.

| Workflow requirement | Implemented evidence | Completion check |
|---|---|---|
| Python/FastAPI backend | `app/main.py`, OpenAPI `/docs`, health API | API test suite passes |
| Command-center frontend | `app/static/index.html`, `styles.css`, `app.js` | Browser can seed, upload, launch, inspect, and report |
| LangGraph or comparable framework | `MissionGraph` dependency-graph runtime | Graph validation and execution-layer tests pass |
| Coordinator and specialized agents | Phase 1 baseline: nine agent implementations | Every graph node completes and persists output |
| Task decomposition/dependency graph | Coordinator plan plus persisted DAG tasks | Architecture endpoint and task graph visible |
| Agent-to-agent communication | Persisted `messages` table and UI tab | Handoffs appear after execution |
| Prompt/context management | `AgentContext`, direct upstream context, persistent shared state | Context remains mission-scoped and reproducible |
| RAG ingestion/retrieval | Multi-format parser, chunking, hybrid retrieval | Uploaded policy is retrieved by relevant query |
| Vector database/embeddings | SQLite chunk vectors and local hash embeddings | Similarity retrieval test passes |
| Source citations | Stable `DOC-id#CHUNK-n` references | Final report includes evidence citations |
| MCP tool server | `/mcp` JSON-RPC plus official SDK adapter | `initialize`, `tools/list`, and `tools/call` tests pass |
| REST API connector framework | Connector registry and API endpoints | Vendor and risk connectors return recorded results |
| Workflow automation | DAG layers, concurrent ready-node execution, lifecycle events | Mission transitions queued → running → completed |
| Vendor-risk demonstration | Sample enterprise policies and vendor profile | End-to-end report produces risk and recommendation |
| Persistent history | SQLite missions/tasks/events/messages/tool calls | History remains available after request completion |

## Phase 1 acceptance test

A successful test must prove that a user can:

1. Upload or seed enterprise documents.
2. Launch a vendor-review mission.
3. Inspect the multi-agent task graph and lifecycle events.
4. See retrieved internal evidence and stable citations.
5. Observe approved MCP/REST tools being called.
6. Open a final evidence-backed report from persisted mission history.
