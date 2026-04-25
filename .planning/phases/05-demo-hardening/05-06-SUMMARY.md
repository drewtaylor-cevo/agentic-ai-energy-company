---
phase: 05-demo-hardening
plan: 06
type: execute
status: complete
completed: 2026-04-25
---

# Plan 05-06 Summary — DEMO-RUNBOOK.md

Presenter-facing single-document demo-day guide is committed at `.planning/phases/05-demo-hardening/DEMO-RUNBOOK.md`. All 6 D-17 sections present with real content, persona values cross-checked against `tests/conftest.py`, and user has approved the §3 cheat-sheet + §5 fallback quote wording.

## Evidence

### Runbook structure

210 lines covering:

1. **Pre-demo setup** — AWS account + Bedrock model access, tag checkout, `npm ci` + venv, stack health check, re-deploy escape hatch, build both dists
2. **Timed checklist (D-19)** — T-24h / T-2h / T-0 subsections
3. **Presenter cheat sheet** — 3-persona table + equal-cards talking point + error-path copy
4. **Launch commands** — `npm run preview` primary, `npm run preview:mock` fallback
5. **Fallback procedure** — "what to say" script + <10s swap steps
6. **Post-demo teardown** — `cdk destroy` in reverse deploy order (Api → Agent → Foundation)

### T-24h gap closure

The D-14/D-15 visual-rehearsal gap logged in `05-VERIFICATION.md known_issues` is explicitly closed by a mandatory checklist item in §2 T-24h:

> **Visual rehearsal (closes D-14/D-15 gap):** open `http://localhost:4173/` in Chrome at 1280×800 with DevTools → Network open, run 2 passes (cold then warm, 30s apart) across all 3 personas plus the `cust999` and `CUST-999` error cases. Record per-persona warm median from DevTools Network Duration. Every warm median must be <3000ms; if not, treat as a gap against UI-02 before presenting.

### Persona values — cross-check vs `tests/conftest.py`

| Persona | Runbook says | conftest.py line:value |
|---------|--------------|------------------------|
| CUST-001 green | $30.00/mo · $360.00/yr | conftest mock_savings_response saving_monthly=30.00 / saving_annual=360.00 |
| CUST-001 cheapest | $55.00/mo · $660.00/yr | conftest mock_savings_response saving_monthly=55.00 / saving_annual=660.00 |
| CUST-002 green | $16.90/mo · $202.80/yr | conftest.py:72 `saving_monthly: 16.90` |
| CUST-002 cheapest | $30.98/mo · $371.76/yr | conftest.py:78 `saving_monthly: 30.98` |
| CUST-003 green | $14.00/mo · $168.00/yr | conftest.py:91 `saving_monthly: 14.00` |
| CUST-003 cheapest | $25.67/mo · $308.04/yr | conftest.py:97 `saving_monthly: 25.67` |

All verbatim. If conftest.py ever drifts, the drift-catch grep in the verify block (`grep -q '16.90' tests/conftest.py` + friends) will fail — the runbook becomes invalid in the same edit that changes the fixture.

### Task 2 — user approval

User read §3 cheat sheet and §5 fallback procedure top-to-bottom and typed `approved`. No rewrites requested. Post-approval structural check passed: all 6 sections, 3 personas with their dollar values, and both launch commands still present.

## Departures from plan template

Three minor adjustments from the template literal:
- Used `--prefix ui` form for npm commands instead of `cd ui && ...`, which avoids shell-state gotchas during a live demo
- Added a preamble "Known gap" callout linking back to `05-VERIFICATION.md known_issues` so the runbook is self-contained about the smoke-derived status of Plan 05
- Added the visual-rehearsal line item to T-24h (not in the plan template) — this closes the gap logged during Plan 05

All structural acceptance criteria still satisfied.

## Self-Check: PASSED

- [x] File exists at `.planning/phases/05-demo-hardening/DEMO-RUNBOOK.md`
- [x] All 6 required top-level sections present
- [x] T-24h / T-2h / T-0 sub-sections under §2 present
- [x] All 3 personas named with correct monthly + annual $ values (cross-checked against conftest.py)
- [x] Launch commands include `npm run preview` (primary) and `npm run preview:mock` (fallback)
- [x] Teardown: 3 `cdk destroy` commands in reverse deploy order (Api, Agent, Foundation)
- [x] Cross-references to `05-DEPLOY-OUTPUTS.md`, `05-VERIFICATION.md`, `04-UI-SPEC.md`, and `REQUIREMENTS.md`
- [x] Frontmatter has `phase: 05-demo-hardening`, `artifact: demo-runbook`
- [x] 210 lines ≥ 150 line minimum
- [x] User approved cheat-sheet wording (Task 2)
- [x] Post-approval structural re-verification: all invariants intact

## Key files

### Created (committed `ef0d298`)
- `.planning/phases/05-demo-hardening/DEMO-RUNBOOK.md`

### Created (this commit)
- `.planning/phases/05-demo-hardening/05-06-SUMMARY.md` — this file

## Cross-reference map

The runbook links to these artifacts so presenter can follow them on demo day:

```
DEMO-RUNBOOK.md
├── §1.1 / §1.4   → aws sts / describe-stacks commands
├── §1.2          → git tag demo-v1.0 (produced by Plan 07)
├── §1.6 / T-0.2  → 05-DEPLOY-OUTPUTS.md (for live ApiEndpoint)
├── §2 T-24h      → 05-VERIFICATION.md (latency table + known_issues)
├── §3 + §5       → ui/src/lib/errors.ts (verbatim error copy)
├── §3 personas   → tests/conftest.py mock_*_response fixtures
├── §4            → ui/package.json scripts (Plan 03)
└── §6            → cdk destroy (not executed in this phase — D-18)
```

## What this unblocks

- **Plan 05-07** can cut `demo-v1.0` — the runbook is committed on the tagged commit, so anyone who checks out `demo-v1.0` has the demo-day guide in their hands.
- **Presenter** has a single document to follow on demo day, including a scheduled visual rehearsal at T-24h that closes the D-14/D-15 gap from Plan 05.
