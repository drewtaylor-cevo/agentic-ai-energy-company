---
phase: 13-bill-shock-multi-tool-flow-agent-01
plan: 08
type: execute
wave: 3
status: partial
completed: 2026-04-29
started: 2026-04-29T12:19:57Z
finished: 2026-04-29T13:04Z
duration_min: 45
autonomous: false
requirements:
  - AGENT-01
  - AGENT-01a
  - AGENT-01b
tags:
  - stack-policy-lift
  - ceremony
  - byte-equivalence-gate
  - freeze-reapply
  - partial-gap-closure

requires:
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plans 01-07)
    provides: Offline-green Phase 13 code — detect_bill_shock_pure, reasoning_trace schema + extractor, 4 @tool wrappers + D-23 system prompt, FourToolCapHook, UI ReasoningTrace, per-flow prewarm gate + D-19/D-21 smoke tests

provides:
  - baseline/pre/{CUST-001,CUST-002,CUST-003}.json — pre-deploy live captures from frozen v2.0/Phase-12 stack
  - baseline/post/{CUST-001,CUST-002,CUST-003}.json — post-deploy live captures (runtime v12)
  - CustomerTariffAgent runtime v10 → v12 (intermediate v11 had the extractor bug)
  - CustomerTariff foundation redeployed (Tools Lambda now serves detect_bill_shock action)
  - Live reasoning_trace surface — 3 entries for all 3 personas; Elena's middle entry byte-different ("Bill shock detected: +$65.16…")
  - Mid-ceremony extractor fix (commit `5644003`): _extract_reasoning_trace now reads _agent.messages slice, not agent_result.message — Strands 1.37 structured_output compat
  - 13-08-CEREMONY-LOG.md — full operator log (pre-flight + lift decision + lift + deploy + post-capture + byte-equivalence + re-apply + post-freeze gaps)

affects:
  - Plan 13-09 (CLAUDE.md addendum) — partially complete; Phase 13.1 needs to add 404 detection + latency invariants
  - Phase 17 freeze-manifest — HEAD SHA 56440032e9f45a73097d9392744e608f0a2e34ae is what lands on the AgentCore runtime v12; freeze manifest will cite this
  - Phase 14 (AGENT-02 hardship) — reuses 4-tool dispatcher and get_hardship_flag tool that are now live
  - **New Phase 13.1 required** — see §Gaps below

tech-stack:
  added: []
  patterns:
    - "CFN get-stack-policy returns StackPolicyBody with an extra trailing \\n\\n vs the source file — Phase 12 precedent established treating this as 'byte-equal (normalised)'. Not a Pitfall 6 trigger."
    - "Strands 1.37 AgentResult.message is LAST turn only; structured_output_model= pushes intermediate tool-use turns into the Agent's conversation history. Extractors must iterate _agent.messages[start:], snapshotting length before each invocation to avoid SC-3 cross-invocation bleed."
    - "Live-deploy ceremony as bug-reveal mechanism — offline tests built synthetic AgentResult objects; only the ECR-image + live-request path surfaced the reasoning_trace: [] regression. Future multi-tool phases need an ECR-image smoke that exercises the real Strands response shape."

key-files:
  created:
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/baseline/pre/CUST-001.json
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/baseline/pre/CUST-002.json
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/baseline/pre/CUST-003.json
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/baseline/post/CUST-001.json
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/baseline/post/CUST-002.json
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/baseline/post/CUST-003.json
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-08-CEREMONY-LOG.md
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-08-SUMMARY.md
  modified:
    - agent/agent.py (extractor fix — commit 5644003)

key-decisions:
  - "Plan 08 originally scripted with a `capture_live_recommendations.py --output-dir --customers` CLI; the actual script has `--mode pre|post|compare` with output hardcoded to Phase 12's baseline dir. Worked around by capturing 5 personas to Phase 12's dir then `cp`-ing CUST-001/002/003 into Phase 13's. Script could be refactored in Phase 13.1 to accept --phase flag."
  - "A-03 sighting-shot resolved as 'deferred-to-in-situ' per operator choice — no dev-alias existed; the prod API was still on Phase 12 code pre-lift, so the measurement had to happen post-deploy. Task 8.7 IS the sighting; it failed. Phase 13.1 remediates with prompt-trim or keepalive-always."
  - "Mid-ceremony extractor bug discovered during byte-equivalence gate evaluation — rather than halt and re-freeze broken, fixed inline (commit 5644003), redeployed CustomerTariffAgent once more (v11 → v12), re-captured + re-verified. Pattern precedent: mid-ceremony fixes are acceptable when SAV-03 is preserved and the fix is obviously non-destructive."
  - "CFN trailing-whitespace artefact on StackPolicyBody — treated as normalised-byte-equal per Phase 12 precedent (not a Pitfall 6 drift)."
  - "Latency + 404 regressions classified as gaps, not blockers to ceremony close. SAV-03 (the ceremony's primary gate) passed. Phase 13.1 will own remediation — lifts the stacks once more with both defects' fixes bundled, avoiding a second lift-deploy-refreeze round inside this ceremony."

requirements-completed: []
  # AGENT-01 (bill-shock multi-tool flow) — DEPLOYED but gated below target. The
  # mechanism is live (trace populated, bill-shock detected, 4-tool cap present);
  # AGENT-01a (p95 < 2500ms) is violated. AGENT-01b (4-tool cap) is live but
  # unexercised in the current latency regime. Phase 13.1 will close.

requirements-partial:
  - AGENT-01: mechanism live; latency gate (AGENT-01a) blocked by multi-tool latency bloat + broken 404 detection

# Metrics
duration: ~45min
completed: 2026-04-29
---

# Phase 13 Plan 08: Stack-Policy Lift + Deploy + Re-Freeze Ceremony Summary

**Phase 13 code deployed to frozen production stacks; SAV-03 byte-equivalence preserved across Sarah/Marcus/Elena; reasoning_trace surface now populated live with 3 entries per persona and Elena's middle entry reveals the designed bill-shock signal — BUT post-freeze latency gate failed (14-20s warm vs 2.5-3.0s targets) and 404 customer-not-found detection now returns HTTP 200 with synthetic UNKNOWN tracks. Ceremony closed with two P0 gaps documented; Phase 13.1 owns remediation.**

## Performance

- **Duration:** ~45 min wall clock
- **Started:** 2026-04-29T12:19:57Z
- **Finished:** 2026-04-29T13:04Z
- **Tasks:** 7 of 7 executed (5 clean + 2 with gaps) — 1 mid-ceremony fix commit
- **Stacks touched:** CustomerTariff + CustomerTariffAgent (2-stack lift; CustomerTariffApi untouched)
- **Runtime versions:** `tariff_agent-O2Hai86N8V` v10 (Phase 12) → v11 (Phase 13 with extractor bug) → **v12 (Phase 13 with fix)** — two agent deploys inside one ceremony, single Tools-Lambda deploy

## Accomplishments

- **Task 8.1 Pre-flight:** Dockerfile COPY directives verified (narrative/ + reasoning/ + hooks/); local ARM64 bi-mode Docker smoke PASS; frozen-policy state confirmed on all 3 stacks; ceremony log initialised.
- **Task 8.2 Pre-capture + cdk diff:** `cdk diff CustomerTariffApi` reported zero differences → 2-stack lift confirmed. 5 personas captured from frozen v2.0/Phase-12 stack; CUST-001/002/003 copied into Phase 13 baseline/pre/ with byte-exact Phase 11 D-13 values ($30/$55 Sarah, $16.90/$30.98 Marcus, $14.00/$25.67 Elena).
- **Task 8.3 LIFT:** Allow-all policies applied + termination protection disabled on CustomerTariff and CustomerTariffAgent. CustomerTariffApi remained `Deny + TP=True` throughout (diff==0).
- **Task 8.4 Deploy:** `cdk deploy CustomerTariff` (26s) rebuilt Tools Lambda asset with Plan 01's `detect_bill_shock` action branch. `cdk deploy CustomerTariffAgent` (25s) pushed new ARM64 container image; runtime v10 → v11. ECR-image bi-mode smoke PASS (Pitfall 4 gate: `reasoning/` + `hooks/` importable from deployed image).
- **Task 8.5 Post-capture + Byte-Equivalence Gate (SAV-03):**
  - Initial post-capture passed byte-equivalence on savings (24/24 SAV-03-sensitive fields) but revealed `reasoning_trace: []` regression across ALL personas despite successful multi-tool execution. Root cause: Strands 1.37's `AgentResult.message` is the LAST turn only; `_extract_reasoning_trace` was reading the wrong source.
  - Fixed inline: added `messages` parameter to extractor; `invoke()` snapshots `_agent.messages` length and passes the new-messages slice (SC-3 mirror — prevents cross-invocation tool-use bleed). Commit `5644003`.
  - Redeployed `cdk deploy CustomerTariffAgent` (runtime v11 → v12).
  - Post-fix re-capture: SAV-03 byte-equivalence still PASSES (24/24 fields); all 3 personas now show 3-entry `reasoning_trace` with correct tool sequence.
  - Elena's middle trace entry: `"Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)"` — byte-different from Sarah/Marcus's `"No bill shock: monthly usage within 11-month envelope"` (C5 cross-persona fabrication signal GREEN).
- **Task 8.6 RE-APPLY freeze:** deny-Update:* policies restored on both lifted stacks; termination protection re-enabled; final-state sweep confirmed Deny + TP=True across all 3 stacks. CFN trailing-whitespace artefact on StackPolicyBody treated as normalised-byte-equal per Phase 12 precedent.
- **Task 8.7 (partial) Post-freeze live sanity:** see §Gaps.

## Gaps (Phase 13.1 scope)

### Gap 1 — Warm latency 5-8× over per-flow gates (P0, AGENT-01a)
`scripts/prewarm.py` post-freeze measurement:
- CUST-001: 17,203ms median vs 3000ms gate — **FAIL (~5.7×)**
- CUST-003: 19,733ms median vs 2500ms gate — **FAIL (~7.9×)**

Root cause hypothesis: Plan 03's preference-ordered 4-tool graph in `_BASE_SYSTEM_PROMPT` causes Claude Sonnet 4.6 to call all 3 pre-tools on **every** customer, not just bill-shock candidates. Evidence: all 3 captured personas show identical 3-entry trace shape (`get_hardship_flag` → `detect_bill_shock` → `simulate_savings`). That's ~3 × 400-900ms per tool round-trip + Bedrock think time + AgentCore microVM overhead → observed 14-20s band.

Remediation options for Phase 13.1 (not chosen here):
- Prompt edit: short-circuit to `simulate_savings` only when `detect_bill_shock` returns `is_shock=False` (drops to 1-2 tools for healthy personas).
- Keepalive-always posture for demos (DEMO-RUNBOOK §T-24h adjustment).
- Accept 4× overrun + revise AGENT-01a SLO to match observed reality.

### Gap 2 — 404 detection broken for unknown customer (P0, REC-03/D-12)
`tests/test_backend_api_smoke.py::test_unknown_customer_returns_404`: expected 404 for `CUST-999`, got HTTP 200 with synthetic UNKNOWN tracks. Manual probe confirmed.

Root cause: `api_lambda/handler.py:152` detects customer-not-found as "no `green` or `cheapest` keys in body" — designed around v1.0/v2.0 agent fallback path returning `{"errorMessage": "..."}`. Plan 03's new multi-tool prompt has the LLM compose a full `RecommendationResponse` with `UNKNOWN` placeholder track data when `get_billing_history` returns empty, so the detection never fires.

Remediation options for Phase 13.1:
- Extend detection: `plan_id=="UNKNOWN"` OR `saving_monthly==0` as additional sentinels.
- Agent-side short-circuit: system prompt instructs LLM to return `errorMessage` shape (not a synthesised track) when billing_history is empty.
- Offline regression test guard locking whichever shape is chosen.

## Task Commits
- Commit `5644003` — `fix(13-08): extractor reads _agent.messages slice, not agent_result.message` (mid-ceremony live-regression fix).
- This SUMMARY + CEREMONY-LOG + 6 baseline JSONs will be committed at ceremony close.

## Post-edit line positions (for Plan 09 + Phase 13.1 reference)

| Symbol | File | Line |
|--------|------|------|
| `_extract_reasoning_trace(..., messages=None)` | agent/agent.py | 383 |
| `_messages_start = len(_agent.messages)` | agent/agent.py | 699 |
| `_extract_reasoning_trace(agent_result, _agent.messages[_messages_start:])` | agent/agent.py | 757/783/810/820 |

## Commit SHA for Phase 17 freeze manifest

Final HEAD at ceremony close: `56440032e9f45a73097d9392744e608f0a2e34ae` (includes the extractor fix).

Live on stacks:
- **CustomerTariff** — Tools Lambda asset `current_account-us-east-1-91672bef`
- **CustomerTariffAgent** — AgentCore runtime `tariff_agent-O2Hai86N8V` version 12, image `sha256:15bb94c16f8f55bb70954da9f0fe3bcd235c855cadd3f369c9dbb77d47bc618d`
- **CustomerTariffApi** — UNTOUCHED (frozen with API Lambda code at `b45b843881f33e5c7ae4cfde7adb23a40bab82d6`)

## Deviations from Plan

1. **Task 8.2 capture script CLI** — Plan 08 described `scripts/capture_live_recommendations.py --output-dir ... --customers CUST-001,CUST-002,CUST-003`; actual script has `--mode pre|post|compare` with output hardcoded to `.planning/phases/12-customerdataprovider-abstraction/baseline/`. Worked around by capturing all 5 personas to Phase 12's dir then `cp`-ing CUST-001/002/003 into Phase 13's dir. No behavioural drift; the captured JSONs are identical. Refactor parked for Phase 13.1 or later.

2. **Sighting decision** — operator chose "deferred-to-in-situ" rather than pre-emptive break-glass (no dev-alias exists; prod API was pre-Phase-13 pre-lift). Task 8.7's prewarm IS the sighting; it failed. Phase 13.1 owns the remedial action — same break-glass option-1 would only cover CUST-003, but CUST-001 is also over-gate now, so the fix must be broader.

3. **Mid-ceremony extractor fix** — live regression surfaced during Task 8.5's initial post-capture; fixed inline (commit `5644003`), redeployed agent container once more, re-captured + re-verified. Not a plan deviation in spirit (SAV-03 still owned the gate), but a second `cdk deploy CustomerTariffAgent` inside a single ceremony window is a new pattern — it works because the lift was still active and the fix was obviously non-destructive.

4. **CFN trailing-whitespace byte-equality** — first policy diff returned exit 1 with a 1-byte trailing-newline difference. Phase 12 precedent (12-06-CEREMONY-LOG.md) treats this as normalised-byte-equal (live policy body content identical to freeze file). Not a Pitfall 6 drift.

5. **Task 8.7 gates** — both per-flow latency gate AND unknown-customer smoke test failed. Plan 08 `<success_criteria>` demanded both PASS to close the ceremony. Operator chose option "close with gaps + Phase 13.1" rather than lift-again-and-fix-inline. Rationale: further lifts compound risk; SAV-03 passed, reasoning_trace works, freeze is re-applied byte-equal — the remaining failures are well-bounded and can be scoped into a dedicated decimal phase.

6. **Stray `agent/.planning/` directory** — early in Task 8.2 the first `mkdir -p .planning/phases/...` ran inside `agent/` (CWD hangover from the Dockerfile build step). Caught and cleaned before any commits. Noted here as a cautionary pattern for future ceremonies — always re-assert CWD between Docker builds and planning-dir operations.

## Auth Gates consumed
- AWS SSO session on `cevo-dev25` (account 588738606436) — valid throughout.
- ECR login via `aws ecr get-login-password` for the ECR bi-mode smoke.
- No new IAM grants required.
