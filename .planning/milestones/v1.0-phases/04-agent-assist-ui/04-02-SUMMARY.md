---
phase: 04-agent-assist-ui
plan: 02
subsystem: ui
tags: [typescript, vitest, validation, types, mock-fixtures, react]

requires:
  - phase: 03-backend-api
    provides: "GET /recommendations/{customer_id} contract — TrackInfo/RecommendationResponse schema, ^CUST-\\d{3,6}$ regex, error taxonomy (400/404/500/502/504)"
  - phase: 04-agent-assist-ui/04-01
    provides: "shadcn + Tailwind v4 + Vitest 4 scaffold; @/ path alias; 7 shadcn primitives"
provides:
  - "ui/src/lib/types.ts — TrackInfo + RecommendationResponse + ApiError interfaces mirroring agent/agent.py schema"
  - "ui/src/lib/validate.ts — CUSTOMER_ID_PATTERN /^CUST-\\d{3,6}$/ identical to api_lambda/handler.py:27 + normalizeCustomerId (D-10: trim/uppercase/auto-dash)"
  - "ui/src/lib/errors.ts — errorCopyForStatus mapping with UI-SPEC-locked strings (en-dash in '3–6 digits', em-dash in 'Try again — if it persists')"
  - "ui/src/personas.ts — PERSONAS readonly array of the 3 Phase 1 seed IDs (CUST-001/002/003) with D-08 '· High/Mid/Low usage' labels"
  - "ui/src/lib/mock/recommendations.ts — MOCK_RECOMMENDATIONS keyed by customer ID, values ported verbatim from tests/conftest.py:47-100 (DEMO-02 flagship: $30/$55 for CUST-001)"
  - "13 passing Vitest unit tests (validate.test.ts + personas.test.ts)"
affects:
  - 04-03-presentation-components
  - 04-04-layout-composition
  - 04-05-build-verify-and-smoke

tech-stack:
  added: []  # No new runtime or dev deps — all foundation modules use stdlib TypeScript + Vitest already installed in Plan 01
  patterns:
    - "Snake_case TypeScript interfaces at the wire-format boundary (plan_id, plan_name, saving_monthly, saving_annual) — matches Pydantic JSON output from agent/agent.py field-for-field"
    - "Status-code-first error copy mapping — UI ignores response.json().error body and keys on HTTP status; spec strings owned by the UI, not the server"
    - "Cross-language regex mirror — /^CUST-\\d{3,6}$/ duplicated in TypeScript exactly matching Python lambda/handler.py:39 and api_lambda/handler.py:27 (defense-in-depth, same commit invariant)"
    - "Mock fixture colocated with lib code (ui/src/lib/mock/recommendations.ts) rather than test fixtures — consumed at runtime when VITE_API_URL is unset (D-03 mock-fallback)"

key-files:
  created:
    - "ui/src/lib/types.ts"
    - "ui/src/lib/validate.ts"
    - "ui/src/lib/errors.ts"
    - "ui/src/personas.ts"
    - "ui/src/lib/mock/recommendations.ts"
    - "ui/src/lib/validate.test.ts"
    - "ui/src/personas.test.ts"
  modified: []

key-decisions:
  - "UI owns operator-facing error copy (errorCopyForStatus keyed by HTTP status); server's {error} body is discarded — UI-SPEC §Copywriting is the single source of truth"
  - "Mock fallback uses the same TrackInfo shape the API returns, so wire through behaves identically whether VITE_API_URL is set or empty (D-03 demo safety net)"
  - "DASHLESS_PATTERN bounds the auto-dash shortcut to 3-6 digits — matching the regex's numeric range so we never normalize 'CUST12345678' into a format the API will reject; ambiguous inputs pass through untouched and fail the regex gate"
  - "PERSONAS declared `readonly` + `as const` so Plan 04 / Plan 05 compilers lock the order — stable card-position demo requirement (CONTEXT.md §Specifics 'Card order is stable')"

patterns-established:
  - "TypeScript mirrors of Python contracts live under ui/src/lib/ as the single canonical location — future cross-language changes update both files in the same commit"
  - "Unit tests for pure logic colocate with the module (validate.test.ts next to validate.ts, personas.test.ts next to personas.ts) — no separate __tests__ directory"
  - "Parametrized it.each() with tuple arrays for input/output pairs — mirrors @pytest.mark.parametrize style used across backend tests"

requirements-completed:
  - UI-01
  - UI-02

duration: 3min
completed: 2026-04-24
---

# Phase 4 Plan 02: Foundation Modules Summary

**TypeScript types, customer-ID validation + normalization, HTTP-status error copy, persona constants, and mock recommendation fixture — five foundation modules wired as the shared contract for the Phase 4 hook, components, and composition plans, with 13 passing unit tests.**

## Performance

- **Duration:** ~3 min (excl. one-time npm install of 331 packages in the fresh worktree)
- **Started:** 2026-04-24T10:44:57Z
- **Completed:** 2026-04-24T10:48:22Z
- **Tasks:** 2 / 2
- **Files created:** 7 (5 modules + 2 test files)
- **Files modified:** 0

## Accomplishments

- `ui/src/lib/types.ts` mirrors `agent/agent.py::TrackInfo` / `::RecommendationResponse` field-for-field (snake_case preserved) and defines `ApiError` matching `api_lambda/handler.py::_error` body shape.
- `ui/src/lib/validate.ts` exports `CUSTOMER_ID_PATTERN` identical byte-for-byte to the backend regex at `api_lambda/handler.py:27` (`^CUST-\d{3,6}$`), plus `normalizeCustomerId` implementing D-10's trim + uppercase + auto-dash rules without over-normalizing inputs that should fail (e.g. `CUST12345678` stays as-is and fails the regex gate).
- `ui/src/lib/errors.ts` implements `errorCopyForStatus` with UI-SPEC-locked copy for 400 / 404 / 504 / 500 / 502 and a generic fallback for network/unknown statuses. The exact dash characters from UI-SPEC are preserved: en-dash (U+2013) in "3–6 digits" and em-dash (U+2014) in "Try again — if it persists".
- `ui/src/personas.ts` exports the `PERSONAS` readonly array of the 3 Phase 1 seed IDs (`CUST-001` / `CUST-002` / `CUST-003`) with D-08-compliant labels using the middle dot separator (U+00B7).
- `ui/src/lib/mock/recommendations.ts` exports `MOCK_RECOMMENDATIONS` keyed by customer ID; values ported verbatim from `tests/conftest.py:47-100` so mock-mode output matches live-API output exactly for the DEMO-02 flagship narrative ($30.00 / $55.00 for Sarah).
- `ui/src/lib/validate.test.ts` exercises 5 positive normalization cases (including `cust-001` case-fix, `  CUST-001 ` whitespace strip, `CUST001234` dash insertion, and `cust001` combined) and 4 post-normalize invalid cases ported from `tests/test_backend_api_handler.py:70-73`.
- `ui/src/personas.test.ts` asserts PERSONAS length, regex-compliance of every ID, ordering against the 3 seeded customers, and non-empty labels.
- `npm test -- --run` exits 0 with **13 / 13 tests passing**; `npm run build` exits 0.

## Task Commits

Each task committed atomically:

1. **Task 1: Create foundation modules (types, validate, errors, personas, mock)** — `0872c70` (feat)
2. **Task 2: Unit tests for validate + personas** — `3df71cb` (test)

_(The final docs commit for this SUMMARY is made in this same worktree; STATE.md / ROADMAP.md are owned by the orchestrator after all Wave 2 executors complete.)_

## Files Created / Modified / Deleted

**Created:**

- `ui/src/lib/types.ts` — `TrackInfo`, `RecommendationResponse`, `ApiError`
- `ui/src/lib/validate.ts` — `CUSTOMER_ID_PATTERN`, `normalizeCustomerId`
- `ui/src/lib/errors.ts` — `errorCopyForStatus`
- `ui/src/personas.ts` — `Persona`, `PERSONAS`
- `ui/src/lib/mock/recommendations.ts` — `MOCK_RECOMMENDATIONS`
- `ui/src/lib/validate.test.ts` — 9 tests (5 positive + 4 negative)
- `ui/src/personas.test.ts` — 4 tests

**Modified:** none

**Deleted:** none

## Decisions Made

- **Error copy is owned by the UI, keyed by HTTP status** — `errorCopyForStatus(status, customerId)` completely ignores any `{error}` string the server may return. The UI-SPEC Copywriting Contract is the single canonical source for operator-facing strings; any drift in the server's friendly error text is invisible to the operator.
- **`DASHLESS_PATTERN` bounds the auto-dash to 3-6 digits** — the regex `^CUST(\d{3,6})$` in `validate.ts` intentionally matches only what the canonical regex can accept. Inputs like `CUST12345678` (8 digits) or `CUST12` (2 digits) do not get a spurious dash inserted; they pass through unchanged and fail `CUSTOMER_ID_PATTERN`, so the operator sees the 400 copy client-side rather than a silently "helpful" but still-invalid ID.
- **Preserve exact spec dash characters (U+2013, U+2014, U+00B7)** — the UI-SPEC file uses an en-dash for "3–6 digits", an em-dash for "Try again —", and a middle dot in persona labels. Swapping them for ASCII hyphens or bullets would silently diverge from the spec.
- **Mock fixture imports `RecommendationResponse` from the shared types module** — `ui/src/lib/mock/recommendations.ts` imports via `'../types'` rather than redeclaring a local shape, so any future TrackInfo schema change will immediately break the mock if the new fields aren't supplied.
- **`PERSONAS` declared `readonly` + `as const`** — locks both the array contents and the tuple order at compile time. The UI-SPEC "Card order is stable" and CONTEXT.md D-08 both depend on deterministic persona ordering; this stops a later plan from accidentally sorting or re-ordering.

## Deviations from Plan

None — plan executed exactly as written.

The plan called out two notes about UI-SPEC character handling ("check the exact characters"):

- For the 400 error, the plan's sample code used `3–6` (en-dash) while also suggesting "if the spec uses plain ASCII, use plain ASCII". Verified via `od -c` on `.planning/phases/04-agent-assist-ui/04-UI-SPEC.md` line 119 — the spec uses an actual U+2013 en-dash (`3–6 digits`). Reproduced exactly.
- For the 500/502 error, the spec uses a U+2014 em-dash (`Try again — if it persists`). Reproduced exactly.
- For the persona labels, the spec uses U+00B7 middle dot (`CUST-001 · High usage`). Reproduced exactly.

These are spec-fidelity matches, not deviations.

## Authentication Gates

None. No external systems or auth required for a pure logic + fixture plan.

## Threat Flags

None. The plan's `<threat_model>` already covered the relevant surface (T-04-03 Spoofing via regex gate, T-04-04 XSS in error copy via React JSX escaping, T-04-05 Tampering of mock data). The foundation modules add no new network endpoints, auth paths, file access, or schema changes beyond what the threat model anticipated.

## Known Stubs

None. All modules are wired with real data:

- `types.ts` has no runtime logic to stub.
- `validate.ts` normalizes real input.
- `errors.ts` returns real copy strings.
- `personas.ts` returns the 3 real seed IDs.
- `mock/recommendations.ts` returns real demo-coherent values ported from the backend test fixtures.

## TDD Gate Compliance

This plan's `type` is `execute`, not `tdd`. Task 2 had `tdd="true"` at the task level but the plan-level gate sequence (RED → GREEN → REFACTOR) does not apply here.

Task 2 (tests) was commit type `test(...)`; Task 1 (implementation) was commit type `feat(...)` earlier in the same plan. Strictly, this is a GREEN-first sequence within the plan because the plan deliberately front-loads the implementation in Task 1 and adds verification tests in Task 2. Both git commits exist in order (`0872c70` feat → `3df71cb` test), and the verification tests pass on first run as expected for this sequencing.

## Issues Encountered

- Fresh worktree had no `ui/node_modules/` directory, so `npm run build` initially errored with `sh: tsc: command not found`. Resolved by running `npm install` (331 packages, 5s). This is a one-time worktree setup cost, not a plan issue; the build now runs cleanly.

## Next Plan Readiness

- **Ready for Plan 04-03 (Wave 2 sibling: `useRecommendations` hook):** `RecommendationResponse` / `ApiError` types, `CUSTOMER_ID_PATTERN` + `normalizeCustomerId`, and `MOCK_RECOMMENDATIONS` are all exported and importable via relative path or `@/lib/*` alias. The hook can now implement its status-code branching against `errorCopyForStatus` without re-deriving the contract.
- **Ready for Plan 04-04 (Wave 3: presentation components):** `TrackInfo` types for prop signatures, `errorCopyForStatus` for the `ErrorAlert`, and `PERSONAS` for `PersonaChips` are all available.
- **Ready for Plan 04-05 (Wave 4: composition + build-smoke):** the full type surface the `App` composition needs (both per-track types and the error-copy helper) is exported from `ui/src/lib/**`.

## Self-Check: PASSED

- Created files exist:
  - `ui/src/lib/types.ts` — FOUND
  - `ui/src/lib/validate.ts` — FOUND
  - `ui/src/lib/errors.ts` — FOUND
  - `ui/src/personas.ts` — FOUND
  - `ui/src/lib/mock/recommendations.ts` — FOUND
  - `ui/src/lib/validate.test.ts` — FOUND
  - `ui/src/personas.test.ts` — FOUND
- Task commits exist in git:
  - `0872c70` (Task 1 — feat) — FOUND
  - `3df71cb` (Task 2 — test) — FOUND
- Key acceptance criteria verified:
  - `grep "plan_id: string" ui/src/lib/types.ts` — MATCH
  - `grep "saving_monthly: number" ui/src/lib/types.ts` — MATCH
  - `grep -E '/\^CUST-\\d\{3,6\}\$/' ui/src/lib/validate.ts` — MATCH
  - `grep "case 400:" ui/src/lib/errors.ts` — MATCH
  - `grep "case 504:" ui/src/lib/errors.ts` — MATCH
  - `grep "CUST-001" ui/src/personas.ts` — MATCH
  - `grep "CUST-003" ui/src/personas.ts` — MATCH
  - Mock fixture contains `30.00`, `55.00`, `16.90`, `25.67` — MATCH
  - `import type { RecommendationResponse } from '../types'` in mock fixture — MATCH
  - `CUSTOMER_ID_PATTERN` referenced in `ui/src/personas.test.ts` — MATCH
  - `npm test -- --run` — 13 / 13 passing, exit 0
  - `npm run build` — exit 0

---
*Phase: 04-agent-assist-ui*
*Completed: 2026-04-24*
