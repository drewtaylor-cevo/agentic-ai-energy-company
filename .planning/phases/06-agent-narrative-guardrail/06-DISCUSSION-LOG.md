# Phase 6: Agent Narrative + Guardrail - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `06-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 06-agent-narrative-guardrail
**Areas discussed:** Validator failure behaviour, Fallbacks + prompt strategy, Banned-terms list ownership

---

## Gray Area Selection

| Gray area offered | Selected |
|-------------------|----------|
| Validator failure behaviour | ✓ |
| Fallbacks + prompt strategy | ✓ |
| Banned-terms list ownership | ✓ |
| Phase 6 test + deploy gate | (deferred to Claude's Discretion during planning) |

---

## Validator Failure Behaviour

### Q1 — Validator rejects narrative string: what should the handler do?

| Option | Description | Selected |
|--------|-------------|----------|
| Swap only narrative fields | Catch ValidationError, swap bad fields to committed fallback, keep numbers intact | |
| Let Strands retry once, then fallback | Retry once on ValidationError (SDK or wrapper), fallback on second failure | ✓ |
| Full-response fallback | Discard response, call simulate_savings directly, assemble from tool + fallback | |
| Sanity-check Strands behaviour first | Add discovery plan to observe Strands' actual retry behaviour before choosing | |

**User's choice:** Let Strands retry once, then fallback.
**Notes:** Accepts a retry latency budget in exchange for a second shot at valid LLM output. Narrows follow-up to ownership of the retry.

### Q2 — Who owns the "retry once" — Strands' built-in retry, or our own wrapper?

| Option | Description | Selected |
|--------|-------------|----------|
| Verify Strands built-in first | Phase 6 researcher confirms SDK behaviour; configure retries=1 if native | |
| Always own the retry in invoke() | Wrap structured_output() in try/except; predictable across SDK upgrades | ✓ |
| Let Strands retry, no wrapper | Assume internal retry, fix forward if wrong | |
| Fail-fast with exception logged | No retry; first miss goes to fallback | |

**User's choice:** Always own the retry in invoke().
**Notes:** Trades a few lines of handler code for SDK independence + greppability. Matches the user's preference for explicit control over a load-bearing path.

### Q3 — When the fallback fires, how visible should it be?

| Option | Description | Selected |
|--------|-------------|----------|
| Log + response marker field | CloudWatch structured log + internal _narrative_source marker stripped by Phase 7 API Lambda | ✓ |
| Log only | CloudWatch log; eval reconstructs fallback detection via string match | |
| Silent fallback | No log, no marker | |
| Log + optional presenter flag | Marker appears only on ?debug=1 | |

**User's choice:** Log + response marker field.
**Notes:** Marker is internal (stripped before client) — gives Phase 9's eval harness a clean assertion path without contaminating the public contract.

### Q4 — If BOTH narrative fields fail validation on the retry, does the handler still return a response?

| Option | Description | Selected |
|--------|-------------|----------|
| Always return response, per-field fallbacks fire independently | Partial-success response always returns 200 | ✓ |
| Both-fail → ?narrative=off-equivalent shape | Omit the fields entirely on double failure | |
| Hard-fail → 500 | Surface HTTP 500 on double failure | |

**User's choice:** Always return response, both fallbacks fire independently.
**Notes:** Per-field fallback is the general rule; double-fail is just two singles. Guarantees the demo always sees v1.0 $30/$55 numbers with narrative copy filled.

---

## Fallbacks + Prompt Strategy

### Q5 — Where do the 6 fallback strings live?

| Option | Description | Selected |
|--------|-------------|----------|
| agent/narrative/fallbacks.json | JSON file keyed by customer_id | |
| agent/narrative/fallbacks.py | Python module with typed constant dict | ✓ |
| Embedded in agent.py | Constant at top of agent.py | |
| DynamoDB-backed | Ops-editable table | |

**User's choice:** agent/narrative/fallbacks.py.
**Notes:** Python module — importable, typed, no JSON-parse step at cold start. Fits the existing agent/ code organisation.

### Q6 — Demo-ready copy or placeholder that Phase 8 polishes?

| Option | Description | Selected |
|--------|-------------|----------|
| Demo-ready copy, written in Phase 6 | 6 production-grade strings, frozen at DEMO-04 | ✓ |
| Placeholder copy, polished in Phase 8 | Ship bland strings; Phase 8 polishes | |
| Demo-ready, reviewed as a separate PR | Dedicated copy-review commit before freeze | |

**User's choice:** Demo-ready copy, written in Phase 6.
**Notes:** Single commit closes the copy risk. No split-phase ownership to drift inside freeze.

### Q7 — What does the LLM see in the prompt?

| Option | Description | Selected |
|--------|-------------|----------|
| Shape-tokens only | Qualitative descriptors; LLM never sees raw kWh or $ | ✓ |
| Tool output pass-through | LLM has simulate_savings + get_billing_history output | |
| Shape-tokens for usage_narrative, tool output for call_script | Split treatment | |
| Shape-tokens + plan_name whitelist | Shape + specific safe fields | |

**User's choice:** Shape-tokens only.
**Notes:** Structural mitigation for PITFALLS.md C1. Strongest possible anti-hallucination gate for numbers.

### Q8 — Where does the shape-token builder live?

| Option | Description | Selected |
|--------|-------------|----------|
| New helper in agent.py / narrative/ module | Pure Python in agent/narrative/shape.py | ✓ |
| Extend simulate_savings tool to return shape | Couples Phase 1 tool to Phase 6 | |
| New @tool the LLM can call | Third tool turn; +300–600ms | |
| Static per-persona file | Breaks under live CRM (v3.0) | |

**User's choice:** New helper in agent/narrative/shape.py.
**Notes:** Pure-function placement — unit-testable, no extra tool turn, no Phase 1 coupling.

### Q9 — How many few-shot exemplars?

| Option | Description | Selected |
|--------|-------------|----------|
| One per card (2 exemplars) | Minimal prompt | |
| One per persona × card (6 exemplars) | Full matrix; +400 tokens | |
| Three exemplars total (one per persona, alternating cards) | Sarah-green, Marcus-cheapest, Elena-green | ✓ |
| Zero exemplars — rules only | Zero-shot | |

**User's choice:** Three exemplars total (one per persona, alternating cards).
**Notes:** Covers all 3 personas + both card tracks without full-matrix prompt bloat.

### Q10 — Where does the narrative prompt content live?

| Option | Description | Selected |
|--------|-------------|----------|
| Inline constant in agent.py | One file to read agent contract end-to-end | |
| agent/narrative/prompt.txt + loader | Externalised text file; review-friendly | ✓ |
| agent/narrative/prompt.py module | Externalised as typed Python constants | |

**User's choice:** agent/narrative/prompt.txt + loader.
**Notes:** Text file avoids Python-string escaping for exemplars; reviewable as prose in PR diff.

---

## Banned-Terms List Ownership

### Q11 — Where does the banned-terms list live?

| Option | Description | Selected |
|--------|-------------|----------|
| agent/narrative/banned_terms.py | Typed Python module | ✓ |
| agent/narrative/banned_terms.json | JSON file | |
| Embedded in validator | Constants inside validator function | |
| agent/narrative/prompt.txt alongside the prompt | Co-located with system prompt | |

**User's choice:** agent/narrative/banned_terms.py.
**Notes:** Matches `fallbacks.py` + `shape.py` convention — all narrative-gate artefacts live in `agent/narrative/`.

### Q12 — How does the validator match banned terms?

| Option | Description | Selected |
|--------|-------------|----------|
| Case-insensitive word-boundary regex | Compiled once per category | ✓ |
| Case-insensitive substring match | Prone to "original"/"origin" false positives | |
| spaCy / NLP lemma match | Heavyweight; inflates Lambda bundle | |
| Exact-string case-sensitive match | Misses case variants | |

**User's choice:** Case-insensitive word-boundary regex.
**Notes:** Right precision/cost trade-off. No new deps — regex is stdlib.

### Q13 — Who enumerates the SWITCH_VERBS and ENV_SUPERLATIVES lists?

| Option | Description | Selected |
|--------|-------------|----------|
| Claude drafts the initial list in Phase 6 | Draft + review in PR; user approves | ✓ |
| You provide the lists upfront | User hands over canonical lists before Phase 6 | |
| Start minimal, expand on eval failures | Ship minimal list; expand in Phase 9 | |

**User's choice:** Claude drafts the initial list in Phase 6.
**Notes:** PR review is the approval gate. Lists locked at merge. No expansion inside DEMO-04 freeze window (CONTEXT D-13).

### Q14 — Banned terms in the prompt too, or validator only?

| Option | Description | Selected |
|--------|-------------|----------|
| Both — prompt + validator | Dual gate: prompt reduces retry rate, validator is hard backstop | ✓ |
| Validator only | Non-enumerated prose in prompt; validator does all the work | |
| Prompt only (validator advisory) | Violates REQUIREMENTS.md UI-05; non-viable | |

**User's choice:** Both — prompt + validator.
**Notes:** Belt-and-braces by design — prompt reduces validator-fail rate (saves retry latency); validator is the non-negotiable UI-05 backstop.

---

## Claude's Discretion (captured in CONTEXT.md)

- Length-cap expression (Pydantic `max_length` + word-count validator interaction on conflict)
- Test + deploy gate timing (single-persona live smoke vs all-three in Phase 6)
- Sample-capture artefact (`06-SAMPLES.md` vs pytest fixture snapshots)
- CloudWatch log detail on fallback fire (log raw LLM output or not)
- Shape-token vocabulary (naming, granularity, attribute composition)
- Pydantic v1 vs v2 confirmation (research-phase sanity check per SUMMARY.md Gaps)

## Deferred Ideas (captured in CONTEXT.md `<deferred>`)

- Presenter tooltip (alt-click reveals raw LLM + verdict) — Phase 7/8
- Haiku fallback path — locked OUT OF SCOPE for v2.0
- Hard in-Lambda timeout budget — Phase 7
- Standalone `SHAPE-TOKENS.md` explainer — Phase 8 design review
- CloudWatch alarm on retry_count > 0 — v3.0
- Phase 9 distributional numeric-token zero-observation eval
</content>
</invoke>
