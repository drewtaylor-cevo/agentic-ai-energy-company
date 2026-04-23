# Phase 3: Backend API - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 03-backend-api
**Areas discussed:** Response delivery model, API gateway flavor, Auth / CORS posture, Request contract + session ID

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Response delivery model | Streaming vs sync, response shape, timeout, warmup | ✓ |
| API gateway flavor | HTTP API vs REST API vs Function URL + stack layout | ✓ |
| Auth / CORS posture | Auth method + CORS policy for Phase 4 UI | ✓ |
| Request contract + session ID | Endpoint shape, session ID origin, error mapping, validation | ✓ |

**User's choice:** All four areas.

---

## Response Delivery Model

### Delivery method

| Option | Description | Selected |
|--------|-------------|----------|
| Sync JSON | Lambda waits for agent, returns single JSON body | ✓ |
| True HTTP streaming (SSE) | Stream partial tokens/events from agent to client | |
| Chunked dual-event stream | Custom: one event for Green, one for Cheapest | |

**User's choice:** Sync JSON.
**Notes:** Roadmap "streaming" phrase interpreted as dynamic recommendations rather than token-by-token streaming; agent uses `structured_output` returning a single JSON object.

### Timeout behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Lambda 30s, 504 on agent timeout | Aligns with API Gateway hard max | ✓ |
| Lambda 60s (requires Function URL) | Beyond API Gateway's 30s limit | |
| Lambda 15s aggressive | Forces fast response or fail fast | |

**User's choice:** Lambda 30s, 504 on agent timeout.

### Warmup strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Accept cold start | No provisioned concurrency / warmer | ✓ |
| Add pre-warm Lambda | Provisioned concurrency or scheduled ping | |

**User's choice:** Accept cold start.
**Notes:** DEMO-03 pre-warm script explicitly deferred to v2 in PROJECT.md.

### Response shape

| Option | Description | Selected |
|--------|-------------|----------|
| Pass-through | Verbatim `{green, cheapest}` from agent | ✓ |
| Wrapped envelope | `{data, meta: {session_id, latency_ms}}` | |

**User's choice:** Pass-through.

---

## API Gateway Flavor

### Gateway type

| Option | Description | Selected |
|--------|-------------|----------|
| API Gateway HTTP API | Cheaper, faster cold start, built-in CORS | ✓ |
| API Gateway REST API | Full-featured, WAF, usage plans | |
| Lambda Function URL | No gateway, simplest streaming | |

**User's choice:** API Gateway HTTP API.

### Stack organization

| Option | Description | Selected |
|--------|-------------|----------|
| New BackendApiStack | Continuation of stack-per-phase pattern | ✓ |
| Extend AgentCoreStack | Fewer stacks, couples API to agent lifecycle | |

**User's choice:** New BackendApiStack.

### ARN wiring

| Option | Description | Selected |
|--------|-------------|----------|
| SSM Parameter from AgentCoreStack | Mirror Phase 1→2 pattern | ✓ |
| CfnOutput import | CloudFormation export dependency (Pitfall 5) | |

**User's choice:** SSM Parameter.

---

## Auth / CORS Posture

### Authentication

| Option | Description | Selected |
|--------|-------------|----------|
| No auth — open endpoint | Demo-only, dummy data, no sensitive info | ✓ |
| Static API key header | Lightweight gate, SSM SecureString | |
| IAM SigV4 | REST API only, heavy for browser demo | |

**User's choice:** No auth — open endpoint.

### CORS policy

| Option | Description | Selected |
|--------|-------------|----------|
| Allow-all origins | `*`, GET/POST, Content-Type header | ✓ |
| Pin to specific origins | Whitelist dev + production origins | |
| Echo request origin | Dynamic origin reflection | |

**User's choice:** Allow-all origins.

---

## Request Contract + Session ID

### Endpoint shape

| Option | Description | Selected |
|--------|-------------|----------|
| GET /recommendations/{customer_id} | Clean REST, idempotent, curl-friendly | ✓ |
| POST /recommendations with body | More flexible, non-idempotent | |
| GET with query string | Less RESTful, no strong reason | |

**User's choice:** GET /recommendations/{customer_id}.

### Session ID origin

| Option | Description | Selected |
|--------|-------------|----------|
| Lambda generates UUID4 per invocation | 36 chars, satisfies AgentCore 33+ minimum | ✓ |
| Client-supplied in body/header | Risks bleed if UI reuses ID | |
| Use API Gateway requestId | Format may not meet 33-char minimum | |

**User's choice:** Lambda generates UUID4 per invocation.

### Error mapping

| Option | Description | Selected |
|--------|-------------|----------|
| Standard mapping (400/404/502/504/500) | REST conventions, distinguishable failures | ✓ |
| All failures → 500 + error body | Simpler code, worse UX | |
| Custom error envelope with code enum | More programmatic, overkill for demo | |

**User's choice:** Standard mapping.

### Input validation

| Option | Description | Selected |
|--------|-------------|----------|
| API Lambda validates, fails fast with 400 | Avoid wasted agent invocation | ✓ |
| Pass through, let agent/tool reject | Simpler, burns agent tokens on bad input | |

**User's choice:** API Lambda validates, fails fast with 400.

---

## Claude's Discretion

Items the user left to Claude during planning:
- CloudWatch log groups, log retention, structured logging format
- X-Ray tracing on the API Lambda
- Lambda memory and Python runtime version
- Exact CDK construct layout (BackendApiConstruct vs inline)
- Test structure and fixture design (must follow Phase 2 `@pytest.mark.smoke` pattern)
- Whether to amend AgentCoreStack for SSM write directly or as a Phase 3 prep step

## Deferred Ideas

- DEMO-03 pre-warm script (remains v2-deferred)
- DEMO-04 frozen environment lock (Phase 5)
- API key / WAF / usage plans (demo doesn't need them)
- Observability polish (X-Ray, structured logs, metrics dashboards) — Claude's discretion
- Multiple deploy stages (dev/staging/prod) — single stage sufficient
- Custom domain / CloudFront fronting — revisit in Phase 4 if needed
