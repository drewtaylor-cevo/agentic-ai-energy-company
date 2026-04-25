---
phase: 04-agent-assist-ui
plan: 05
type: summary
status: complete
self_check: PASSED
completed: 2026-04-24T11:00:00Z
commits:
  - 8fb56bc
files_created: []
files_modified:
  - ui/src/App.tsx
requirements_satisfied:
  - UI-01
  - UI-02
---

# 04-05 — App Composition & 1280px Smoke

## What was built

Replaced the placeholder `App.tsx` (from 04-01) with the production composition that wires
together the entire Phase 4 stack: `useRecommendations` hook (04-03), the six presentation
components (04-04), the persona chips data (04-02), and the shadcn primitives (04-01).

The composed page is the single source of user-visible behavior for Phase 4:

- "Tariff Recommendations" heading (28px, Inter semibold) with a two-column equal-cards grid.
- `LookupForm` with a `Customer ID` label + `e.g. CUST-001234` placeholder (D-11) that calls
  `lookup(customerId)` on submit.
- `PersonaChips` renders the three demo personas (`CUST-001`, `CUST-002`, `CUST-003`) as
  click-to-query shortcuts for the retention conversation demo.
- State-driven render: `idle → EmptyState`, `loading → RecommendationSkeletons` (same grid
  slot as the final cards for zero layout shift), `error → ErrorAlert` (replaces the cards
  entirely), `success → two RecommendationCards` with `track="green"` and `track="cheapest"`
  props feeding the accent-only visual diff (emerald `#16A34A` vs blue `#2563EB`).
- Equal-cards contract enforced at the grid layer — both cards receive identical width and
  padding; visual differentiation is accent color + badge only (no ranking, no hierarchy).

## Verifications

| Check | Result |
| ----- | ------ |
| `npm run build` | exit 0 (1848 modules, `dist/assets/index-BQOccTBh.js` 235.30 kB / gzip 74.18 kB) |
| `npm test -- --run` | 30 / 30 passing |
| `grep` — all 6 component imports + `useRecommendations` + both `track=` props + page title | PASS |
| `main.tsx` does not import `App.css` | PASS (removed in 04-01 per D-15) |
| `grep -r "dangerouslySetInnerHTML" ui/src` | 0 matches (T-04-12 XSS mitigated) |
| Task 2: 1280×800 smoke test (9 steps, all 3 personas + error paths + normalization + layout shift) | PASSED by human verification 2026-04-24 |

### Task 2 human-verify detail (all 9 steps passed)

1. Viewport 1280×800 — Chrome DevTools device toolbar ✓
2. Idle state — heading, labelled input with `CUST-001234` placeholder, 3 persona chips, "No customer selected" empty state ✓
3. CUST-001 Sarah — Green `$30.00/mo · $360.00/yr · EcoFlex 100` + Cheapest `$55.00/mo · $660.00/yr · Value 12`, both above the fold, equal-cards contract honored ✓
4. CUST-002 Marcus — Green `$16.90/mo` + Cheapest `$30.98/mo`, both above fold ✓
5. CUST-003 Elena — Green `$14.00/mo` + Cheapest `$25.67/mo`, both above fold ✓
6. Invalid format 400 — `That doesn't look like a customer ID. Format is CUST followed by 3–6 digits.` (en-dash preserved) ✓
7. Mock-miss 404 — `No customer found for CUST-999. Check the ID and try again.` ✓
8. Normalization D-10 — `cust001` → `CUST-001` → Sarah's cards ✓
9. Layout shift — skeletons occupy same grid slot as cards, zero reflow ✓

## Self-Check

PASSED — UI-01 (both cards above the fold at 1280px) and UI-02 (skeleton-first rendering,
never blank) verified end-to-end. Equal-cards contract, error copy, and client-side
normalization all confirmed against the live preview build.

## Commits

- `8fb56bc` feat(04-05): compose App.tsx with state-driven rendering

(No SUMMARY.md commit yet — this file is committed by the orchestrator after the checkpoint
clears, together with the Wave 4 tracking update.)

## Deviations

None. `main.tsx` needed no change (already clean from Plan 04-01). Plan executed exactly
as written for Task 1; Task 2 was a human-verify gate and required no code work.

## Known gaps / follow-ups

None for Phase 4 itself. Phase 5 (Demo Hardening) will layer a live `VITE_API_URL` pointing
at the deployed backend (Phase 3) for the end-to-end rehearsal, plus the frozen-environment
lock. The mock fallback path exercised during this smoke will remain as a demo-day safety
net.
