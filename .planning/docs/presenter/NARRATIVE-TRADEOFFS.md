# Narrative Tradeoffs — What You Give Up When the LLM Writes the Copy

> **Audience:** Presenter, product owner, compliance reviewer.
> **Purpose:** Honest acknowledgement of the cost-vs-value of LLM-generated narrative in a regulated customer communication context.

---

## What the LLM Produces

Two short text fields per recommendation track:

| Field | Purpose | Cap | Example |
|-------|---------|-----|---------|
| `usage_narrative` | Third-person description of the customer's usage profile | ≤20 words / 140 chars | "Strong cool-season usage with a family-sized load across the year." |
| `call_script` | Second-person one-liner the operator reads verbatim | ≤22 words / 180 chars | "Ask about EcoFlex — it suits a strong winter-heating profile like yours." |

These fields are the only LLM-generated content in the entire response. Dollar figures, plan names, plan IDs, and methodology text are all deterministic.

---

## What You Gain

### 1. Personalised Framing Without Manual Copywriting
Each customer's usage profile is different — seasonal peaks, consumption level, household size. The LLM reads the billing shape (via tool output, not raw data) and produces a contextual framing that a human copywriter would need to write per-persona. At scale (thousands of customers), this is the difference between "generic template" and "feels like someone looked at my account."

### 2. Operator Confidence
The call script gives the operator a natural opening line. Without it, the operator sees two cards with numbers and has to improvise the conversation. The script bridges the gap between "data on screen" and "words to say."

### 3. Adaptability to New Personas
When a new customer archetype is added (solar PV, EV charging, hardship), the LLM adapts its framing without new template authoring. The fallback bank provides a safety net, but the model handles the long tail.

---

## What You Give Up

### 1. Determinism
The same customer looked up twice may get different narrative text. The dollar figures are identical (deterministic engine), but the wording varies. This is by design — the LLM is a generative system — but it means:
- **You cannot screenshot a narrative and guarantee it will appear again.** The fallback bank provides stable copy if needed.
- **A/B testing narrative quality requires capturing the model output**, not just the customer ID. The `_narrative_source` marker (visible in logs, stripped from client responses) tracks whether each field came from the model or the fallback.

### 2. Latency
The LLM adds 1–3 seconds to the response time. The deterministic savings engine alone returns in <500ms. The narrative layer is the dominant contributor to the UI-02 <3s contract. Mitigations:
- Pre-warm scripts exercise the full path before demo/production use
- The `?narrative=off` kill switch collapses the UI to v1.0 shape (no narrative, no LLM call overhead in the response rendering)
- Fallback strings are instant (no LLM round-trip when the fallback fires)

### 3. Validation Overhead
Every LLM output passes through the D-15 dual-gate (Pydantic structural + banned-terms regex). When validation fails:
- First retry: lenient schema parse → per-field salvage (keep clean fields, swap dirty ones)
- Second failure: full fallback to committed strings

This means ~5–15% of invocations (model-dependent) serve fallback copy instead of fresh narrative. The fallback copy is good — it was written by a human and passes all validators — but it is generic rather than personalised.

### 4. Content Risk Surface
Despite the dual-gate, the LLM output is a content risk surface that does not exist in a pure-template system:
- **Tone drift:** The model may produce copy that is technically valid (passes all validators) but tonally off — too casual, too formal, or awkwardly phrased. The word/char caps constrain length but not quality.
- **Banned-term evolution:** The current banned list covers 6 competitors, 28 switch verbs, and 12 environmental superlatives. New competitors, new marketing terms, or regulatory changes require manual list updates.
- **Model upgrades:** Changing the underlying model (currently Claude Sonnet 4.6) can alter narrative quality, tool-use behaviour, and validation pass rates. The D-22 Strands pin and model-literal pin exist specifically to prevent accidental regressions.

### 5. Audit Complexity
In a pure-template system, every customer-facing string is committed in source control. With LLM narrative:
- The **fallback strings** are committed and auditable ([`agent/narrative/fallbacks.py`](../../../agent/narrative/fallbacks.py))
- The **model-generated strings** are logged but not pre-committed — audit requires log analysis, not code review
- The `_narrative_source` marker distinguishes the two in every response

---

## The Honest Framing for a Reviewer

> "We chose to let the LLM write two short text fields — a usage description and a call script — because the alternative is maintaining a template library that scales linearly with customer archetypes. The tradeoff is non-determinism in those two fields, mitigated by a banned-terms regex, word/char caps, and a per-persona fallback bank. The dollar figures, plan names, and methodology are fully deterministic and never touch the LLM. If the narrative layer misbehaves, a single URL flag collapses the UI to the deterministic-only shape without a redeploy."

---

## Decision Matrix: When to Use Each Mode

| Scenario | Recommended Mode | Rationale |
|----------|-----------------|-----------|
| Standard demo / production | Narrative ON (default) | Personalised framing adds value; validators catch issues |
| Compliance review / audit | Narrative ON + capture `_narrative_source` from logs | Reviewer sees both model and fallback paths |
| High-stakes presentation (board, regulator) | `?narrative=off` | Eliminates LLM variability; deterministic-only surface |
| Model upgrade testing | Narrative ON + run eval harness (`test_narrative_eval_live.py`) | Validates new model against existing validator rules |
| New persona onboarding | Narrative ON + add fallback strings first | Fallback bank is the safety net while the model learns the archetype |

---

*Document: DOC-02 (REQUIREMENTS.md). Committed as part of Phase 16 (Presenter Artefacts + Operational Consolidation).*
