# Phase 13: Bill-Shock Multi-Tool Flow (AGENT-01) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 13-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-29
**Phase:** 13-bill-shock-multi-tool-flow-agent-01
**Areas discussed:** Tool surface + bill-shock threshold, reasoning_trace shape + API pass-through, 4-tool cap mechanism + D-04 fallback body, UI ReasoningTrace + mock fixtures + ?narrative=off, Per-flow prewarm gate + system prompt + stack lift + Pitfall C5 prevention

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Tool surface + bill-shock threshold | Tools to land + numeric threshold + intent trigger | ✓ |
| reasoning_trace shape + API pass-through | Entry shape, attachment, extraction failure contract | ✓ |
| 4-tool cap mechanism + D-04 fallback body | Cap enforcement + cap-fire response body + pytest | ✓ |
| UI ReasoningTrace + mock fixtures + ?narrative=off | Placement, kill-switch honour, mock fixture pattern | ✓ |

**User's choice:** All four. Scope extended naturally to cover per-flow prewarm gate + system prompt + stack lift + Pitfall C5 discipline (all load-bearing and explicitly named in ROADMAP SC + invariant ownership — not scope creep).

---

## Tool Surface + Bill-Shock Threshold

### Which tools should land as @tool wrappers in Phase 13?

| Option | Description | Selected |
|--------|-------------|----------|
| detect_bill_shock (Recommended) | New @tool + detect_bill_shock_pure helper | ✓ |
| get_billing_history (Recommended) | New @tool wrapping existing Lambda action | ✓ |
| get_customer_profile (skip) | Defer — optional per research | ✓ (skip) |
| get_hardship_flag (co-land here) | Co-land wrapper so Phase 14 adds only guard + union | ✓ |

**User's choice:** detect_bill_shock + get_billing_history + get_hardship_flag co-landed. Skip get_customer_profile.
**Notes:** Research lists get_customer_profile as optional; CUST-002 demo narrative doesn't require segment-level framing. Co-landing get_hardship_flag wrapper here (tool only, no guard) makes Phase 14 strictly about the discriminated union + pre-LLM guard.

### What is the numeric definition of 'bill shock'?

| Option | Description | Selected |
|--------|-------------|----------|
| \|monthly_delta\| > 30% of 11-month mean (Recommended) | Symmetric threshold, portable across personas | ✓ |
| absolute: \|monthly_delta\| > $25 | Non-portable across baseline sizes | |
| % delta > 25% AND absolute > $15 | Dual-gate hybrid | |
| % delta > 50% OR > $40 | Looser — risks missing Marcus spike | |

**User's choice:** 30% of 11-month mean, symmetric.
**Notes:** 11-month mean excludes the test month (avoids self-inclusion bias). Symmetric so both over- and under-consumption trigger.

### How is the bill-shock flow intent triggered?

| Option | Description | Selected |
|--------|-------------|----------|
| LLM-decides from prompt (Recommended) | System prompt describes preference-ordered tool graph | ✓ |
| Rep-selected intent (URL param) | Deterministic, but adds UI surface + API contract | |
| Always-on multi-tool | Maximum trace theatre; worst latency | |
| Auto-detect per-customer | Hard-coded persona list, brittle | |

**User's choice:** LLM-decides.
**Notes:** Matches v2.0 style (agent decides when to call simulate_savings). Avoids new UI intent contract.

---

## reasoning_trace Shape + API Pass-Through

### What shape should each reasoning_trace entry take?

| Option | Description | Selected |
|--------|-------------|----------|
| {tool, summary} minimal (Recommended) | Two fields; code-composed in Python | ✓ |
| {tool, args, summary} with args | Exposes customer_id each entry | |
| {tool, args, result, ts} full raw dump | Large surface; redundant dollar figures | |
| {tool, summary, duration_ms} with per-tool latency | Strands doesn't surface timing natively | |

**User's choice:** {tool, summary} minimal.
**Notes:** Smallest public surface; easiest pytest coverage; SAV-03-safe by construction.

### How is reasoning_trace attached to the response body?

| Option | Description | Selected |
|--------|-------------|----------|
| Top-level alongside green/cheapest (Recommended) | Parallel shape; simple UI consumption | ✓ |
| Nested under each track | Duplicates turn-level data | |
| Nested in meta object | Breaks existing _narrative_source strip | |

**User's choice:** Top-level.

### How does the extraction helper handle failures?

| Option | Description | Selected |
|--------|-------------|----------|
| Always list; empty on failure (Recommended) | Simple UI + API contract | ✓ |
| Return None on failure | Adds null branch to contract | |
| Raise on failure | Couples concerns with fallback path | |

**User's choice:** Always return a list.

### How are reasoning_trace summary strings composed?

| Option | Description | Selected |
|--------|-------------|----------|
| Code-composed from tool result (Recommended) | Extractor Python formatters; SAV-03 by construction | ✓ |
| Tool @ wrapper returns data + summary | Risks LLM re-using pre-formatted summaries | |
| LLM generates summaries via structured_output | EXPLICITLY breaks SAV-03 | |

**User's choice:** Code-composed. New per-tool formatters in `agent/reasoning/summaries.py` (or inline per Claude's discretion).

### Does D-15 (banned terms) apply to reasoning_trace summaries?

| Option | Description | Selected |
|--------|-------------|----------|
| No — trace is exempt (Recommended) | Observability, not sales copy; intentionally contains digits/$ | ✓ |
| Yes — apply D-15 to summaries | Rejects every useful summary; kills the feature | |
| Partial — switch-verb + competitor only | Over-engineering for code-generated surface | |

**User's choice:** Exempt.
**Notes:** Explicit CLAUDE.md addendum documents the exemption + a counter-pytest asserts digits/$ pass validation on the trace surface.

### Does api_lambda/handler.py pass reasoning_trace through, or validate it?

| Option | Description | Selected |
|--------|-------------|----------|
| Pass through unchanged (Recommended) | Mirrors green/cheapest; API Lambda stays dumb | ✓ |
| Pass through with shape validation | Duplicates Pydantic schema | |
| Strip on ?narrative=off only | Kill switch is UI-side already | |

**User's choice:** Pass through unchanged.

---

## 4-Tool Cap Mechanism + D-04 Fallback

### How is the 4-tool cap enforced in code?

| Option | Description | Selected |
|--------|-------------|----------|
| Agent(max_iterations=4) Strands primitive (Recommended) | Leverages native Strands 1.37 feature | ✓ |
| Wrapper counter around _agent() call | Bypasses Strands primitive | |
| Both — belt-and-braces | Over-engineering | |

**User's choice:** Strands max_iterations=4.
**Notes:** Planner must confirm Strands 1.37.0 exact exception / stop_reason semantics during research.

### What does the response body look like when the cap fires?

| Option | Description | Selected |
|--------|-------------|----------|
| Existing D-04 fallback + partial reasoning_trace (Recommended) | Reuse proven never-500 path | ✓ |
| New dedicated cap-exhausted body with cap_fired marker | Duplicates _narrative_source observability | |
| Truncate + succeed with partial | Half-reasoned response violates determinism | |

**User's choice:** Existing D-04 fallback path.

### What does the pytest for the cap assert?

| Option | Description | Selected |
|--------|-------------|----------|
| Offline crafted infinite-delegator (Recommended) | Deterministic; no live dependency | ✓ |
| Live smoke test against Bedrock | Expensive + flaky (Sonnet 4.6 avoids loops) | |
| Both — offline + live smoke | Partial live covered by Phase 16 DEMO-10 canary | |

**User's choice:** Offline only.

---

## UI ReasoningTrace + Mock Fixtures + ?narrative=off

### Where does ReasoningTrace sit in the layout?

| Option | Description | Selected |
|--------|-------------|----------|
| Single row above both cards (Recommended) | Collapsed disclosure; zero vertical cost | ✓ |
| Inline in each RecommendationCard (per-track) | Duplicates turn-level data; fights Area 2 | |
| Below both cards as footer row | Violates UI-01 at 1280×800 | |
| Floating side panel / drawer | Overbuilds; drawer is Phase 15 territory | |

**User's choice:** Single row above both cards.

### How does ReasoningTrace honour ?narrative=off?

| Option | Description | Selected |
|--------|-------------|----------|
| Hidden entirely (null render) (Recommended) | LD-7 single-flag contract; matches v2.0 pattern | ✓ |
| Rendered but always-collapsed | Still costs 1 row; violates LD-7 | |

**User's choice:** Hidden entirely (null render).

### How are mock fixtures for reasoning_trace handled?

| Option | Description | Selected |
|--------|-------------|----------|
| Byte-exact canonical mock matching backend formatter (Recommended) | Single source of truth; emergency path works | ✓ |
| Minimal mock (empty trace) | Defeats dist-mock demo story | |
| CUST-002 only; others empty trace | Most accurate to real behaviour; more fixture to maintain | |

**User's choice:** Byte-exact canonical mock.
**Notes:** Non-bill-shock personas get `reasoning_trace: []`; CUST-002 gets the 3-entry byte-exact trace matching `summaries.py` formatter output.

---

## Per-Flow Prewarm Gate + Latency Discipline

### How does prewarm.py split the warm-median gate?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-flow gates — 3000ms single-tool / 2500ms multi-tool (Recommended) | LD-4 explicit; diagnostic on failure | ✓ |
| Single global 2500ms — tightened | No headroom for single-tool drift | |
| Single global 3000ms — unchanged | Multi-tool budget too loose | |

**User's choice:** Per-flow gates.

### Phase 13 or Phase 16 adds the per-flow gate?

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 13 adds mechanism; Phase 16 extends rotation (Recommended) | ROADMAP SC #3 explicitly scopes Phase 13 | ✓ |
| Phase 13 pytest-only; Phase 16 owns prewarm | Conflicts with ROADMAP | |

**User's choice:** Phase 13 ships mechanism + 2-persona rotation.

---

## System Prompt Extension

### How does the system-prompt extension land?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend _BASE_SYSTEM_PROMPT in place (Recommended) | Single source; matches existing assembly | ✓ |
| Separate bill_shock_prompt.txt loaded conditionally | Agent has two personalities; confusing | |
| New file via prompt_loader appended | Still requires editing _BASE for rule 1 change | |

**User's choice:** Edit _BASE_SYSTEM_PROMPT directly.
**Notes:** Retain rules 2–7 VERBATIM (numeric-integrity clauses). Planner writes final prose within D-23's structural bounds.

---

## Stack-Policy Lift + Pitfall C5 Prevention

### Which frozen stacks need the stack-policy lift?

| Option | Description | Selected |
|--------|-------------|----------|
| All three: CustomerTariff + Agent + Api (Recommended) | Safest default; drop Api if cdk diff==0 | ✓ |
| Only CustomerTariff + CustomerTariffAgent | api_lambda pass-through = no code change | |

**User's choice:** Default plan all three; downgrade to two if `cdk diff CustomerTariffApi == 0` at planning time.

### How is Pitfall C5 (fabrication regression) prevented?

| Option | Description | Selected |
|--------|-------------|----------|
| Cross-persona canary test CUST-002 + CUST-004 offline (Recommended) | Phase 06.1 pattern; deterministic | ✓ |
| CloudWatch tool-invocation counter (Recommended) | Zero invocations = fabrication | ✓ |
| Latency-floor witness > 1000ms (Recommended) | Sub-1s response is suspicious | ✓ |
| Freeze Strands 1.37.0 (Recommended) | Any bump requires decimal phase + re-canary | ✓ |

**User's choice:** All four. Multi-layered defence — Phase 06.1 taught us no single signal is sufficient.

---

## Claude's Discretion

- Exact Strands 1.37.0 exception/stop_reason taxonomy for `max_iterations` exhaustion — planner research pin.
- `agent/reasoning/summaries.py` as new module vs inline function — planner picks.
- `_extract_reasoning_trace` location (`agent/agent.py` vs new `agent/reasoning/extractor.py`) — planner picks.
- Crafted-loop pytest mechanism (monkey-patched agent vs self-referential test tool) — planner picks.
- Test file organisation (one `test_bill_shock_flow.py` vs split) — planner picks.
- Smoke-marker granularity (`-m smoke` only vs new `-m latency`) — planner picks.
- Exact wording of `_BASE_SYSTEM_PROMPT` edits within D-23 structural bounds — planner writes.
- Whether `capture_live_recommendations.py` is promoted to `scripts/` or stays in `.planning/phases/13-*/` (reuse Phase 12 D-06 decision).
- Whether new @tools route via `_provider` or via direct `_lambda_client.invoke` (default is direct to keep Protocol 3-method clean per LD-5).

## Deferred Ideas

- `get_customer_profile` tool — v3.1 if needed
- Rep-selected flow intent (`?flow=bill_shock`) — deferred escape valve
- SSE / streaming trace — breaks Config(read_timeout=25)
- SequentialToolExecutor — rehearsal-contingent escape valve
- Provisioned Concurrency on Tools Lambda — accept cold first-call latency
- `cap_fired: true` response marker — use _narrative_source observability
- ReasoningTrace drawer pattern — Phase 15 territory
- CustomerDataProvider Protocol extensions — LD-5 3-method discipline
- Full 5-persona prewarm rotation — Phase 16 DEMO-09
- Live cap smoke test — Phase 16 DEMO-10 canary covers
- Typed hardship categories (AGENT-03) — v3.1
- Presenter DOC-01/02/03 reasoning-trace references — Phase 16
- `bedrock-agentcore` dep bump — Phase 15 single permitted bump
