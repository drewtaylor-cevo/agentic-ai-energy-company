# Phase 7: API Pass-Through + Pre-Warm Route - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 07-api-pass-through-pre-warm-route
**Areas discussed:** Pre-warm route shape, Alias + Provisioned Concurrency wiring, Marker strip + pass-through mechanics, Pre-warm failure semantics + persona rotation

---

## Pre-warm Route Shape

### Q1: Where does `?prewarm=1` live?

| Option | Description | Selected |
|--------|-------------|----------|
| Same route, flag + seed customer_id | `GET /recommendations/{customer_id}?prewarm=1` — handler branches on query flag. Same route pattern, same IAM, same integration. customer_id still required but becomes a throwaway seed when prewarm=1. Matches ARCHITECTURE.md Option (b). | ✓ |
| Dedicated `/prewarm/{customer_id}` route | New API Gateway route + route-specific Lambda integration (same Lambda fn). Cleaner URL; adds freeze-surface route + needs additional IAM path. | |
| Bodyless `/prewarm` (no customer_id) | `GET /prewarm` — handler picks its own seed from env var or hardcoded rotation. Simplest operator UX but handler now owns seed-selection which adds freeze surface. | |
| Query flag on root `/` | Literally follows SC-2 wording. Requires a new `GET /` route that only exists for demo-day warming — over-indexing on a typo in the success criterion. | |

**User's choice:** Same route, flag + seed customer_id
**Notes:** Matches ARCHITECTURE.md §DEMO-03 Option (b) "warms exactly what the demo will hit." customer_id regex (D-13) still validates first — stray `?prewarm=1` with bad customer_id returns 400, not 204. Consistent fast-fail for both modes.

### Q2: When prewarm=1, what does the handler execute against the agent runtime?

| Option | Description | Selected |
|--------|-------------|----------|
| Full real agent turn, body discarded | Identical `invoke_agent_runtime` call a normal lookup would run; discard response body; return 204. Warms Lambda + microVM + Bedrock + simulate_savings + Strands + Pydantic. ~2.5s per call. | ✓ |
| Stripped-down "hello" turn | Payload bypasses the tool path. Faster (~800ms) but warms less. | |
| Chain both — full first, cheap keep-alive after | First call full; subsequent within 5 min stripped. Premature optimisation; belongs in Phase 9 keep-alive if at all. | |

**User's choice:** Full real agent turn, body discarded
**Notes:** Matches ARCHITECTURE.md Open Question 1 recommended answer. Exercises the exact hot path the demo will hit 10 minutes later.

### Q3: Persona rotation owner?

| Option | Description | Selected |
|--------|-------------|----------|
| Operator script rotates 3 personas | `scripts/prewarm.py` (Phase 9) curls `?prewarm=1` × 3 with 2s spacing. Handler stateless. Warms microVM pool depth. | ✓ |
| Handler round-robins internally | Handler ignores seed customer_id and picks its own. One operator call warms all. Adds handler state; one 502 poisons the whole warm. | |
| Single seed, operator chooses | Backend warms whatever customer_id was passed. Flexible; relies on runbook discipline. | |

**User's choice:** Operator script rotates 3 personas
**Notes:** Keeps Lambda handler stateless. Matches ARCHITECTURE.md §DEMO-03 data flow diagram.

### Q4: Pre-warm downstream failure behaviour?

| Option | Description | Selected |
|--------|-------------|----------|
| Always 204, log the failure | All exceptions caught → 204 + structured CloudWatch log (`prewarm_failed=true`). SC-2 emphatic that prewarm NEVER 5xx. | ✓ |
| 204 on success, 204-with-warning-header on failure | Adds `X-Prewarm-Status: warn` header. More observable from CLI; adds contract surface. | |
| 204 with body on failure | Body contains `prewarm_failed=true` JSON. Technically satisfies SC-2; binds operator script to a response schema. | |

**User's choice:** Always 204, log the failure
**Notes:** Keeps demo-day loud failures out of presenter terminal. Operator script's `curl -f` always sees success; CloudWatch is the canonical observability channel.

---

## Alias + Provisioned Concurrency

### Q5: How does `demo_pc` CDK context flag control PC?

| Option | Description | Selected |
|--------|-------------|----------|
| Alias always exists, PC only when `-c demo_pc=N` | Named alias `live` always created + API Gateway targets it. `demo_pc` defaults to 0 (no PC). `-c demo_pc=1` attaches ProvisionedConcurrencyConfiguration. Idempotent; alias never moves. | ✓ |
| Alias only when PC=1 | Alias conditional; integration target swaps. API Gateway integration ARN changes between modes — would conflict with Phase 10 freeze stack policies. | |
| Alias always, PC always-on with `demo_pc` sizing | PC always configured. Expensive; FEATURES.md explicitly rejected always-on PC. | |

**User's choice:** Alias always exists, PC only when `-c demo_pc=N`
**Notes:** Freeze-surface-critical — integration ARN never changes, so CFN `Update:*` deny at Phase 10 doesn't block PC toggling.

### Q6: Alias version tracking?

| Option | Description | Selected |
|--------|-------------|----------|
| CDK `current_version` auto-publish; alias tracks current | `fn.current_version` auto-publishes on code change; `alias = fn.add_alias('live', version=fn.current_version)`. PC auto-warms new version. | ✓ |
| Manually pinned version per deploy | Alias version as CDK context. Forces explicit thought; overkill for demo stack. | |
| Alias tracks `$LATEST` | Not possible — Lambda aliases must point at numbered versions. | (non-option) |

**User's choice:** CDK `current_version` auto-publish; alias tracks current
**Notes:** Matches AWS Lambda alias best practice. Simplest, idempotent.

### Q7: Alias name + integration target?

| Option | Description | Selected |
|--------|-------------|----------|
| `live`, API Gateway always targets alias | AWS convention; future-proof for v3.0 production. Integration ARN never changes. | ✓ |
| `demo`, API Gateway targets alias | More honest to current purpose; would need renaming at v3.0. | |
| `current`, API Gateway targets alias | Neutral description of behaviour; less conventional. | |

**User's choice:** `live`, API Gateway always targets alias
**Notes:** Future-proof and convention-aligned.

### Q8: PC semantics of `-c demo_pc=N`?

| Option | Description | Selected |
|--------|-------------|----------|
| `demo_pc=N` sets PC count to N; `demo_pc=0` removes PC config | Integer-valued flag. `demo_pc=1` sets PC=1; default (0) omits PC entirely. Presenter can type `demo_pc=2` if back-to-back depth needed. | ✓ |
| Boolean flag — `demo_pc=1` = on, anything else = off | Simpler mental model; locks PC at 1 forever. | |
| `demo_pc=on` / `demo_pc=off` keyword flag | String-valued; less CDK-native. | |

**User's choice:** `demo_pc=N` sets PC count to N; `demo_pc=0` removes PC config
**Notes:** Integer-valued gives presenter escape hatch (`demo_pc=2`) without code change. PC=1 is the typical freeze value.

---

## Marker Strip + Pass-Through

### Q9: How to strip `_narrative_source`?

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit `body.pop('_narrative_source', None)` | One line, idempotent, greppable. `None` default handles missing marker gracefully. | ✓ |
| Whitelist-based rebuild | Reconstruct response as `{"green": ..., "cheapest": ...}`. Strictest; any future schema addition requires API Lambda change. | |
| Deep copy + pop at nested levels | Walk response, pop everywhere. Defensive; over-engineered for a contract that pins marker to one location. | |

**User's choice:** Explicit `body.pop('_narrative_source', None)`
**Notes:** Idempotent. Pre-6.1 deployments or future agent revisions that drop the marker don't break the handler.

### Q10: Log `_narrative_source` values before stripping?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, structured log on every successful invocation | `{"customer_id": ..., "narrative_source": {"usage_narrative": "model"|"fallback", "call_script": "model"|"fallback"}}` at INFO. Free observability for Phase 9 eval harness. Zero PII. | ✓ |
| Only log when any field is `fallback` | Suppresses happy path. Phase 6 already logs `narrative_fallback_fired=true` at agent layer. | |
| No log — marker stripped silently | Minimalist. Loses end-to-end marker propagation visibility during demo-day debugging. | |

**User's choice:** Yes, structured log on every successful invocation
**Notes:** Gives Phase 9's eval harness CloudWatch-queryable record of model-vs-fallback across the full API path.

### Q11: Narrative pass-through mechanics?

| Option | Description | Selected |
|--------|-------------|----------|
| Byte-identical pass-through, zero field awareness | Existing `json.dumps(body)` already flows new fields. Only change this phase makes: pop marker + log. Matches Phase 3 D-02 invariant. | ✓ |
| Validate narrative fields before returning | Assert fields present non-empty. Duplicates Phase 6 Pydantic validation. | |
| Unit-test assertion only (no runtime check) | Add offline test; no runtime validation. Same result + test coverage. | |

**User's choice:** Byte-identical pass-through, zero field awareness
**Notes:** Lowest change surface. Phase 6 Pydantic validator is the authoritative gate.

### Q12: Test structure?

| Option | Description | Selected |
|--------|-------------|----------|
| New test + extend existing | Add `test_narrative_pass_through`, `test_prewarm_returns_204` alongside existing tests in `test_backend_api_handler.py`. | ✓ |
| Extend `test_backend_api_handler.py` only | Add new test functions to the existing file. File grows past review size. | |
| New `test_api_v2.py` | Separate file. Overkill for a small delta. | |

**User's choice:** New test + extend existing
**Notes:** Clean separation; follows existing per-module convention.

---

## Pre-Warm Failure Semantics + Persona Rotation (remaining follow-ups)

### Q13: Prewarm timeout budget?

| Option | Description | Selected |
|--------|-------------|----------|
| Inherit existing 25s read_timeout | Same `_agentcore_client` with existing `Config(read_timeout=25, connect_timeout=5)`. On timeout: `ReadTimeoutError` caught → 204 + log. | ✓ |
| Dedicated shorter read_timeout (e.g. 15s) for prewarm | Two clients; fail-fast on prewarm. Marginal benefit. | |
| Hard handler-side timer with `signal.alarm` | Way overkill for a demo prewarm. | |

**User's choice:** Inherit existing 25s read_timeout
**Notes:** No new config surface. One client.

### Q14: Phase 7 live verification of prewarm?

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 7 smoke: one-shot curl of `?prewarm=1` per persona | Post-`cdk deploy`, curl all 3 personas → 204, CloudWatch shows `narrative_source` log on subsequent lookups. Pinned as closeout gate. Phase 9 wraps into `scripts/prewarm.py`. | ✓ |
| Phase 7 ships `scripts/prewarm.py` too | Pulls DEMO-03 tooling half into Phase 7 — REQUIREMENTS.md Traceability explicitly keeps it in Phase 9. | |
| Phase 7 pytest smoke marker test | Mixes Phase 7 smoke with Phase 9 eval harness target. | |

**User's choice:** Phase 7 smoke: one-shot curl of `?prewarm=1` per persona
**Notes:** Good separation — Phase 7 proves the Lambda works; Phase 9 delivers operator UX.

### Q15: UI-02 (<3s warm) verification in Phase 7?

| Option | Description | Selected |
|--------|-------------|----------|
| Warm-median check inside the Phase 7 live smoke | 3 warm lookups per persona with `curl -w "%{time_total}"`, assert median <3s. Matches ROADMAP SC-4. | ✓ |
| Defer UI-02 check to Phase 9 eval harness | Risk: Phase 7 could break UI-02 without detection for 2 phases. | |
| Defer to T-24h DevTools rehearsal only | Failure surfaces with nowhere to pivot. | |

**User's choice:** Warm-median check inside the Phase 7 live smoke
**Notes:** Phase 7 cannot close without proof that narrative payload preserves UI-02.

---

## Claude's Discretion

Areas where the planner has flexibility (see CONTEXT.md Claude's Discretion section):

- Structured log format (JSON vs key=value — recommended JSON, matches Phase 6)
- How `demo_pc` context is read (construct-level vs kwarg from stack — recommended construct-level)
- Whether to export `demo_pc` as `CfnOutput` (recommended no)
- Whether prewarm uses a distinct uuid4 session prefix (recommended vanilla uuid4, no new session shape)
- Post-deploy wait before warm-median check (≥3 min for PC to provision)
- Exact per-persona latency thresholds in D-15 (default <3000ms median; may tighten to <2500ms on flagship)

## Deferred Ideas

See CONTEXT.md `<deferred>` section — 12 items including `scripts/prewarm.py` (Phase 9), end-to-end eval harness (Phase 9), explicit `/prewarm` route (rejected in D-01), always-on PC (rejected in FEATURES.md + D-11), and presenter debug tooltip (Phase 8, requires marker to survive — conflicts with Phase 7 D-06).
