# Phase 6: Agent Narrative + Guardrail - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the Strands agent's `TrackInfo` Pydantic model with `usage_narrative` + `call_script` string fields, add the `field_validator` that hard-rejects digits, currency symbols (`$`, `£`, `€`, `%`), and banned terms (switch verbs, named competitors, environmental superlatives), commit per-persona × per-card fallback strings, and deploy to AgentCore in `us-east-1` — preserving the v1.0 `$30` / `$55` DEMO-02 deltas exactly.

**In scope (Phase 6 only):**
- `TrackInfo` schema extension + `field_validator` + length caps
- Shape-token builder that derives qualitative descriptors from billing history (so the LLM never sees raw kWh or dollar figures in the narrative prompt)
- Externalised system-prompt additions + 3 few-shot exemplars
- Committed fallback strings (3 personas × 2 cards = 6 strings), demo-ready copy
- Banned-terms list (Python module, case-insensitive word-boundary regex)
- Retry-once-then-per-field-fallback policy owned in `invoke()`
- Pytest covering poisoned-string injection, validator + fallback behaviour, numeric-token absence
- Live deploy to AgentCore + single-shot live smoke per persona (sample capture)

**Out of scope (moved to later phases):**
- API Lambda pass-through (Phase 7) — API Lambda strips the `_narrative_source` marker before returning to client
- UI rendering, skeleton rows, feature flag, version indicator (Phase 8)
- Pre-warm tooling, `demo-keepalive.sh`, end-to-end eval harness across all personas × cards (Phase 9)
- Freeze artefacts + rollback drill (Phase 10)

New capabilities (streaming narrative, regenerate button, second LLM critique, model swap) are out of scope for v2.0 entirely — see `REQUIREMENTS.md` Out of Scope table.

</domain>

<decisions>
## Implementation Decisions

### Validator Failure Behaviour
- **D-01:** On `ValidationError` from the narrative `field_validator`, the handler catches the exception in `invoke()` and issues exactly **one** retry of `structured_output()` with the same prompt. On second failure, swap the offending narrative field to the committed fallback string. Retry is owned in `invoke()` — not delegated to Strands — for predictability, greppability, and survival across Strands SDK upgrades. (Reason: Strands' retry-on-`ValidationError` behaviour is MEDIUM-confidence per `.planning/research/SUMMARY.md` Gaps; owning the retry removes the unknown.)
- **D-02:** Fallback is **per-field**, not per-response. If `usage_narrative` fails but `call_script` passes (or vice versa), only the failing field swaps to fallback. If both fail, both swap independently. Response always returns 200 with v1.0 `$30` / `$55` numbers intact — numbers are never at risk from a narrative miss.
- **D-03:** When a fallback fires, emit (a) a CloudWatch structured log entry with `narrative_fallback_fired=true`, the field name, persona/`customer_id`, and card track; AND (b) an internal response marker field `_narrative_source: {"usage_narrative": "model"|"fallback", "call_script": "model"|"fallback"}`. The marker is **stripped by the API Lambda in Phase 7** and never reaches the UI — it exists so Phase 9's eval harness can assert end-to-end which path fired for each request.
- **D-04:** Under no circumstances does Phase 6 return HTTP 500 or an empty-narrative response on validation failure. The fallback strings are themselves guaranteed validator-passing (enforced by a dedicated pytest).

### Fallbacks + Prompt Strategy
- **D-05:** Fallback strings live in `agent/narrative/fallbacks.py` as a typed Python constant dict keyed by `customer_id` → `{"green": {"usage_narrative": str, "call_script": str}, "cheapest": {"usage_narrative": str, "call_script": str}}`. Imported once at agent module load. Frozen alongside other demo artefacts at DEMO-04.
- **D-06:** The 6 fallback strings are **demo-ready copy**, written during Phase 6 against the persona profiles in `infrastructure/seed_data/billing_records.py` (Sarah / Marcus / Elena). They are not placeholders — Phase 8 does not re-author them. They must pass every rule the `field_validator` enforces (checked by a dedicated pytest).
- **D-07:** The LLM sees **shape-tokens only** in the narrative prompt — never raw kWh figures, never dollar values. Shape-tokens are qualitative descriptors (e.g. `winter_heavy`, `summer_peak`, `usage_tier=high`, `renewable_profile=eco_aligned`) derived in pure Python from `get_billing_history` output + the plan attributes. This makes it *structurally impossible* for the model to quote figures it was never given (PITFALLS.md C1 — primary mitigation).
- **D-08:** The shape-token builder is a new pure-Python helper in `agent/narrative/shape.py` — `build_shape_tokens(billing_history, plan) -> dict[str, str]`. Called from `invoke()` *before* the prompt is assembled. Unit-testable without AWS credentials.
- **D-09:** Three few-shot exemplars total — one per persona, alternating cards so both tracks are represented in the corpus: Sarah-green, Marcus-cheapest, Elena-green. Middle-ground prompt size (vs. 2-total or 6-total full matrix). Exemplars demonstrate voice, length cap, no-numbers rule.
- **D-10:** The extended system prompt (narrative rules + exemplars) lives in `agent/narrative/prompt.txt`, loaded once at agent module import by a small `load_prompt()` helper. Externalising avoids Python-string-escaping pain for exemplars, makes copy review cleaner in a PR diff, and lets the prompt be frozen as an independent artefact at DEMO-04.

### Banned-Terms List
- **D-11:** Banned-terms list lives in `agent/narrative/banned_terms.py` as three Python tuple constants: `COMPETITORS`, `SWITCH_VERBS`, `ENV_SUPERLATIVES`. Imported by the validator. Frozen alongside the prompt at DEMO-04.
- **D-12:** `COMPETITORS` is locked from `.planning/research/SUMMARY.md`: `("Origin", "AGL", "EnergyAustralia", "Red Energy", "Alinta", "Momentum")`. Non-negotiable (regulator-visible risk).
- **D-13:** `SWITCH_VERBS` and `ENV_SUPERLATIVES` are **drafted by Claude in Phase 6 planning** and reviewed in the PR diff before merge. Starting set for `SWITCH_VERBS` should cover: switch, move, change, transfer, swap, shift, convert (and common inflections). Starting set for `ENV_SUPERLATIVES` should cover: greenest, cleanest, most sustainable, carbon-neutral, zero-emission, net-zero, best for the planet (and similar framings). Expand during PR review; do not expand inside the DEMO-04 freeze window.
- **D-14:** Matching is **case-insensitive word-boundary regex**, compiled once per category at module load: `re.compile(r"\b(term1|term2|…)\b", re.IGNORECASE)`. Avoids substring false positives ("original" ≠ "origin"), ~50 µs per validation. No spaCy / NLP dependency (keeps Lambda bundle slim and freeze surface small).
- **D-15:** Banned terms are **both** injected as a negative constraint in the system prompt ("NEVER use these words: …") AND hard-enforced by the `field_validator`. Dual gate — prompt reduces validator-fail rate (saves retry latency), validator is the non-negotiable backstop per REQUIREMENTS.md UI-05. This is belt-and-braces by design.

### Claude's Discretion
- **Length caps (words + chars).** REQUIREMENTS.md sets word caps (`usage_narrative` ≤20, `call_script` ≤22); ARCHITECTURE.md suggests char caps (140 / 180). Planner decides how to express both in the Pydantic model (e.g. `Field(max_length=…)` + a word-count `field_validator`) and which number wins on conflict. Default to the stricter of the two.
- **Test + deploy gate timing.** Whether Phase 6 closes on a live deployed-AgentCore smoke across all 3 personas (invoked via boto3 `invoke_agent_runtime`), or hands off live verification to Phase 7's API layer. Phase 6 success criterion 5 requires *the deployed image in us-east-1* serves the extended schema — so at minimum a single-persona live smoke is required. Planner decides test corpus size for poisoned-string injection (recommend ≥3 per banned category).
- **Sample-capture artefact.** Whether Phase 6 produces a `06-SAMPLES.md` file with captured live-smoke output for design review, or keeps samples in pytest fixture snapshots. Either satisfies traceability.
- **Retry logging detail.** Whether the CloudWatch log on fallback fire includes the raw rejected LLM output (for debug) or only the validation failure reason. Default: log the failure reason + persona/card, NOT the raw output (PII / prompt-injection surface minimised; PITFALLS.md M7).
- **Shape-token vocabulary.** Exact set of descriptors `build_shape_tokens` emits — naming conventions, granularity (3-level vs continuous), and how plan attributes (`renewable_profile`, `rate_tier`) compose with usage attributes. Planner decides the vocabulary; must be documented in `shape.py` as the contract fed to the LLM.
- **Pydantic version sanity-check.** SUMMARY.md Gaps flags "confirm Pydantic v2 is what Strands pulls (not v1)". Planner verifies during research-phase before committing to `field_validator` syntax (v2 uses `@field_validator` decorator; v1 uses `@validator`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Phase Spec
- `.planning/REQUIREMENTS.md` — Read §"Agent-Assist LLM Narrative (UI)" for UI-03, UI-04, UI-05 full text. Locked decisions at requirements stage (same-turn Claude 3.7 Sonnet, feature flag + `demo-v1.0` tag + `build:mock` rollback) are in the "Key Decisions Locked at Requirements Stage" table.
- `.planning/ROADMAP.md` §"Phase 6: Agent Narrative + Guardrail" — 5 success criteria. All 5 must be TRUE before Phase 7 begins.
- `.planning/PROJECT.md` — Core value, constraints, v1.0 shipped state summary, and the "Recommendation design" invariant (Green + Cheapest never ranked against each other).

### v2.0 Research (the source for Option A, validator placement, banned-terms rationale)
- `.planning/research/SUMMARY.md` §"Phase 2.1: Agent Narrative + Guardrail" — phase rationale and research flags (Strands retry-on-ValidationError behaviour, Pydantic v2 confirmation, model choice open question).
- `.planning/research/SUMMARY.md` §"Gaps to Address" — open questions the planner must resolve (narrative model choice, system prompt location, FREEZE-MANIFEST format).
- `.planning/research/ARCHITECTURE.md` §"UI-03 / UI-04 — Generation Strategy" — Option A vs B vs C comparison (Option A is locked). §"Hallucination Control (Option A — Prompt-Level)" defines the three prompt-level rules.
- `.planning/research/ARCHITECTURE.md` §"Latency Budget — Does UI-02 Survive v2.0?" — the 1470–3150ms warm envelope; AP-2 (no second call) and AP-6 (no length-cap drift) are load-bearing for Phase 6.
- `.planning/research/STACK.md` — Strands SDK version, Pydantic version, Bedrock model ID pin.
- `.planning/research/PITFALLS.md` — C1 (dollar contradictions), C3 (length drift), C5 (silent retries), M7 (PII in logs), AP-1 (free-form prose instead of structured fields), AP-3 (cached session IDs).
- `.planning/research/FEATURES.md` — "should-ship" features including persona-of-voice lock, hard in-Lambda timeout budget, narrative telemetry.

### v1.0 Carry-Forward (the stack Phase 6 extends)
- `agent/agent.py` — the existing Strands agent. Current `TrackInfo` model (lines 32–37) is the extension target. Existing `SYSTEM_PROMPT` (lines 82–96) is the extension target. Existing `invoke()` entrypoint with the fallback path (lines 117–148) is where the retry-once-then-per-field-fallback policy wires in.
- `agent/requirements.txt` — `strands-agents==1.37.0`, `bedrock-agentcore==1.6.3`, `boto3>=1.42.0`. Phase 6 adds no new runtime deps beyond what Strands already pulls (Pydantic).
- `lambda/handler.py` — Phase 1 `simulate_savings_pure` + `get_billing_history`. Phase 6 shape-token builder consumes the same billing-history shape this Lambda produces. Read before writing `build_shape_tokens`.
- `infrastructure/constructs/agent_runtime.py` — AgentCore runtime construct. IAM is scoped to `lambda:InvokeFunction` on ToolsLambda + `bedrock:InvokeModel`. Phase 6 requires **no new IAM permissions** — only code inside the existing runtime container changes.
- `infrastructure/agentcore_stack.py` — the CDK stack that builds and deploys the agent container. `cdk deploy AgentCoreStack` re-builds the image and rolls the AgentCore runtime.
- `agent/Dockerfile` — agent container build. `COPY agent/ /app/agent/` already includes any new `agent/narrative/` subdirectory (verify during planning).
- `infrastructure/seed_data/billing_records.py` — the three persona profiles (Sarah CUST-001, Marcus CUST-002, Elena CUST-003) that fallback strings must be written against.

### v1.0 Phase Context (for pattern + convention carry-forward)
- `.planning/milestones/v1.0-phases/02-agentcore-agent/02-CONTEXT.md` — Phase 2 decisions on Strands / AgentCore / Claude 3.7 Sonnet / IAM scoping. The invariants this phase extends.
- `.planning/milestones/v1.0-phases/02-agentcore-agent/02-VERIFICATION.md` (if present) — Phase 2 gate evidence. Phase 6 must not regress these.

### Test Reference Patterns
- `tests/test_agent_tools.py` — offline mocked-Strands test pattern. Phase 6 poisoned-string tests should follow the same `MagicMock` + `json.dumps` fixture approach.
- `tests/test_agent_smoke.py` — live `invoke_agent_runtime` smoke pattern. Phase 6 live-smoke test extends this.
- `tests/test_schema.py` — existing Pydantic schema test pattern; Phase 6 validator tests live alongside.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/agent.py` `TrackInfo` model (lines 32–37) — extend in place; add `usage_narrative: str` and `call_script: str` with `Field(..., max_length=…)` and `@field_validator`. Do NOT mark the new fields `Optional` — the response contract guarantees they are always present (fallback on validator failure, not optional omission).
- `agent/agent.py` `SYSTEM_PROMPT` (lines 82–96) — append loaded narrative rules + exemplars from `agent/narrative/prompt.txt`.
- `agent/agent.py` `invoke()` entrypoint (lines 117–148) — wire retry-once-then-per-field-fallback logic here. The existing `try/except` (L130–148) is a *tool-failure* fallback (direct Lambda call if `structured_output` errors); the new narrative fallback is different — it triggers on `ValidationError` from the validator, not on an agent execution error. Keep the two paths distinct.
- `tests/conftest.py` — existing `mock_savings_response` fixture (used by `test_agent_tools.py`) is reusable for mocking `structured_output` return.

### Established Patterns
- **Pure-helper + boto3-wrapper split.** `lambda/handler.py` already isolates pure logic (`simulate_savings_pure`) from boto3-touching code. Phase 6 `build_shape_tokens` follows the same pattern — pure function, unit-testable without AWS.
- **Module-level init for reused clients / constants.** `agent.py` instantiates `_lambda_client`, `_model`, `_agent` at module load. Phase 6 loads prompt text, compiles banned-term regexes, and parses the fallbacks dict at module load too — zero per-invocation overhead.
- **Pytest fixtures keyed on persona customer_id.** `tests/conftest.py` conventions use `CUST-001` / `CUST-002` / `CUST-003` directly. Phase 6 tests reuse the same IDs.
- **Logging via `logger = logging.getLogger(__name__)` + `logger.info`/`logger.warning`.** Already in `agent.py` line 20. CloudWatch structured-log markers for fallback fire follow the same pattern.

### Integration Points
- **Downstream contract (Phase 7):** API Lambda must strip the `_narrative_source` internal marker from the response before returning to client. This is noted here for Phase 7's CONTEXT.md — planner flags it explicitly.
- **Downstream contract (Phase 9):** End-to-end eval harness asserts `_narrative_source` values across 10 invocations × 3 personas × 2 cards. Harness needs a boto3-direct path to AgentCore (not through the API Lambda) so the marker is readable.
- **No IAM change.** The existing AgentCore runtime role has `lambda:InvokeFunction` on ToolsLambda + `bedrock:InvokeModel` on the Claude 3.7 Sonnet model. Phase 6 needs nothing else.
- **No new CDK stack.** `AgentCoreStack` is the deploy target; `cdk deploy AgentCoreStack` rebuilds the container with the new `agent/narrative/` files and rolls the runtime.

</code_context>

<specifics>
## Specific Ideas

- **The "numbers come from the tool, words come from the LLM, and the two must never meet in the prompt" rule is load-bearing.** Shape-tokens are the mechanism: the LLM literally cannot quote a figure it was never shown. The validator is the safety net if the rule somehow leaks (e.g. an exemplar accidentally includes `$30`). Both layers exist because either alone is insufficient.
- **Fallback strings must themselves pass the validator.** Write a dedicated pytest that imports the `FALLBACKS` dict, runs every string through the `field_validator`, asserts no exceptions. Non-negotiable — if a fallback string contains a digit, the double-fail path becomes an exception source.
- **The internal `_narrative_source` marker is not a schema change exposed to the client.** Phase 7's API Lambda strips it. Phase 8's UI never sees it. Phase 9's eval harness sees it only by calling AgentCore directly via boto3, bypassing the API layer. This is intentional — it gives eval visibility without contaminating the public contract.
- **Per-persona fallback copy references the plan name but NOT numbers.** Example for Sarah / green / `call_script`: *"Ask about EcoFlex 100 — it suits a strong winter-heating profile like yours."* No dollar figure, no kWh, no percent. Plan name is safe (string field from tariff catalogue, not a savings figure).
- **Phase 6 success criterion 5 requires the deployed image in us-east-1 — so Phase 6 includes `cdk deploy AgentCoreStack`.** This is unusual (v1.0 Phase 2 also deployed). Planner must include the deploy step, a post-deploy live smoke, and a capture of sample output before the phase closes.
- **Do not regress v1.0 tests.** The full `pytest -m "not smoke"` suite (81 passed / 6 skipped at v1.0 close) must remain green. Any Phase 6 test that requires live Bedrock must be marked `@pytest.mark.smoke` so the offline suite is unaffected.

</specifics>

<deferred>
## Deferred Ideas

- **Presenter tooltip (alt-click reveals raw LLM + verdict).** FEATURES.md flagged this as should-ship. Belongs in Phase 8 (UI work) — needs the `_narrative_source` marker to survive the API Lambda, which is a Phase 7 contract decision. Capture here and revisit in Phase 7/8 CONTEXT.
- **Haiku fallback path.** Locked OUT OF SCOPE for v2.0 per REQUIREMENTS.md. Only revisit if Phase 6 live-smoke shows the same-turn Sonnet approach breaches the UI-02 <3s budget with pre-warm applied.
- **Hard in-Lambda timeout budget (narrative <1500ms else fallback).** FEATURES.md should-ship. Belongs in Phase 7 (API Lambda) — Phase 6's agent runtime doesn't own the Lambda-side clock.
- **Shape-token documentation as a standalone reference.** The vocabulary `build_shape_tokens` emits is the contract between Python and the LLM; it could be worth a short `agent/narrative/SHAPE-TOKENS.md` explainer. Defer to Phase 8 design review if the 3-persona demo highlights a need.
- **CloudWatch alarm on `retry_count > 0` (PITFALLS.md C5 mitigation).** Needs CloudWatch metric filter + alarm CDK. Demo-irrelevant (single-shot presentation) — belongs in v3.0 production hardening.
- **FEATURES.md anti-feature "LLM quoting dollar figures" reinforcement tests.** Beyond the Phase 6 poisoned-string injection suite, the Phase 9 eval harness will assert zero numeric tokens across 10 × 3 × 2 live invocations. Phase 6 covers the unit level; Phase 9 covers the distribution.

</deferred>

---

*Phase: 06-agent-narrative-guardrail*
*Context gathered: 2026-04-25*
</content>
</invoke>