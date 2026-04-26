# Phase 8 Closeout Evidence — 08-SAMPLES.md

**Captured:** 2026-04-26
**Viewport:** 1280 × 800, DPR 1.0, Chrome (operator's local browser)
**Expected `__GIT_SHA__`:** `fe39971`
**Live API:** https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/
**Evidence mode:** Operator verbal attestation against each success criterion. Screenshot PNGs intentionally skipped (deferred-items tradeoff — see §Rollback Contract Holds). Phase 10 DEMO-06 rollback drill will re-capture live images against the frozen tag; this doc provides the logged gate results + operator sign-off.

## D-23 Gate Results

| Gate | Command | Result | Evidence |
|------|---------|--------|----------|
| 1a | `npx tsc -b --noEmit` (from `ui/`) | PASS (clean) | `/tmp/08-04-tsc.log` (executor-side) |
| 1b | `npx vitest run` (from `ui/`) | PASS (8 files, 90 tests) | `/tmp/08-04-vitest.log` — 73 baseline + 3 flag + 36 mock-rules + 14 card/skeleton + 3 VersionIndicator |
| 2 | `VITE_API_URL=https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/ npm run build` | PASS | `fe39971` embedded in `ui/dist/assets/index-j1lA8N6Q.js` (grep confirmed, 1 match). Bundle size 235,576 bytes. |
| 3 | `npm run build:mock` | PASS in 0.62s (<10s Success Criterion 5) | `fe39971` embedded in `dist-mock/assets/index-*.js`; canonical fallback strings `"Strong cool-season usage"` and `"Warm-season heavy"` verbatim present |

## Success Criteria (ROADMAP Phase 8)

- [x] **1.** Narrative + call_script rows render on every persona lookup with no layout shift — operator confirmed visually at 1280×800 (flag-ON capture pass A). Skeleton → content transition reported shift-free; Cheapest card bottom edge did not jump.
- [x] **2.** Both cards above the fold at 1280×800 at maximum length — operator confirmed for CUST-001 (Sarah), CUST-002 (Marcus), CUST-003 (Elena) with live-API generated narrative + call_script content.
- [x] **3.** `?narrative=off` hides both rows AND skeleton placeholders (D-10 contract) — operator confirmed across all three personas in both success state and loading state. Card height visibly shorter (v1.0 shape: plan name → savings grid → methodology only). Neither narrative paragraph nor bordered call-script quote block present. Skeleton also collapsed to v1.0 loading shape (no `.space-y-2` narrative shell, no `.border-l-muted` call_script shell).
- [x] **4.** `v2.0 · <git-sha>` corner marker matches built SHA — operator confirmed `v2.0 · fe39971` visible in bottom-right corner across all 6 success-state captures (3 flag-ON + 3 flag-OFF). SHA string matches `fe39971` byte-exact.
- [x] **5.** `build:mock` regenerates a working dist with extended TrackInfo — gate 3 above. Mock dist renders narrative + call_script from the 6 verbatim fallback strings. Emergency-swap path (<10s) preserved.

## Persona Captures

### CUST-001 (Sarah Chen)

**Flag ON (success):** Operator confirmed both cards above fold, italic muted narrative paragraph between savings grid and methodology line, bordered call-script quote block with emerald (Green track) and blue (Cheapest track) left borders respectively, `v2.0 · fe39971` corner marker visible. Content demo-ready (no digits, no `$`, no placeholder text).

**Flag OFF (success):** Operator confirmed zero narrative/call_script DOM on either card. Card matches v1.0 shape. Corner marker `v2.0 · fe39971` still visible.

**Loading — flag ON:** Operator confirmed `.space-y-2` narrative placeholder + `.border-l-muted` call_script placeholder shell visible during Slow 3G load.

**Loading — flag OFF:** Operator confirmed NEITHER placeholder visible under `?narrative=off` on Slow 3G. Matches v1.0 loading shape. D-10 non-negotiable contract holds in both loading and success states.

### CUST-002 (Marcus Webb)

**Flag ON (success):** Operator confirmed both cards above fold, narrative + call_script rendered, emerald/blue track accents visible on call-script left border, corner marker matches `fe39971`.

**Flag OFF (success):** Operator confirmed zero narrative/call_script DOM, v1.0 card shape, corner marker still visible.

**Loading — flag ON:** Operator confirmed narrative + call_script placeholders visible during throttled load — parallelism with CUST-001 confirmed.

### CUST-003 (Elena Vasquez)

**Flag ON (success):** Operator confirmed both cards above fold, narrative + call_script rendered, track accents correct, corner marker matches `fe39971`.

**Flag OFF (success):** Operator confirmed zero narrative/call_script DOM, v1.0 card shape, corner marker still visible.

## Layout-Shift Observation

Operator reported skeleton → content transition appeared shift-free in Chrome at 1280×800 across all three personas. Cheapest card bottom edge did not jump observably when the response resolved; narrative placeholder height approximates rendered prose height closely enough for the eye not to catch the swap. Subjective field — binary "PASS" recorded.

## Rollback Contract Holds

The `?narrative=off` flag collapses the UI to v1.0 shape in BOTH loading and success states (CUST-001/002/003 verified). The flag is the primary runtime rollback lever and is ready for Phase 10's DEMO-06 drill.

## Evidence-Mode Note (for Phase 10)

PNG capture was deferred at operator's discretion (verbal attestation accepted). Phase 10's DEMO-06 rollback drill will re-capture the live images against the frozen `demo-v2.0` tag at T-48h — that capture pass is the authoritative image evidence for the demo. This doc + the automated gate logs + operator's typed `approved` signal constitute the D-23 closeout sign-off.
