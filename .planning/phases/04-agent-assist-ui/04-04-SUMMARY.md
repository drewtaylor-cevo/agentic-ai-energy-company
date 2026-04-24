---
phase: 04-agent-assist-ui
plan: 04
subsystem: ui
tags: [react, shadcn, lucide, accessibility, equal-cards, tdd-not-applicable]

requires:
  - phase: 04-agent-assist-ui/04-01
    provides: "shadcn primitives (button, input, card, label, skeleton, alert, badge) + cn() + @ alias + lucide-react"
  - phase: 04-agent-assist-ui/04-02
    provides: "ui/src/lib/types.ts (TrackInfo), ui/src/lib/errors.ts (errorCopyForStatus), ui/src/personas.ts (PERSONAS)"
provides:
  - "ui/src/components/RecommendationCard.tsx — single component renders both Green and Cheapest tracks via TRACK_CONFIG; enforces UI-SPEC §Color equal-cards contract"
  - "ui/src/components/ErrorAlert.tsx — shadcn destructive Alert keyed by errorCopyForStatus"
  - "ui/src/components/EmptyState.tsx — idle-state copy verbatim from UI-SPEC §Copywriting"
  - "ui/src/components/RecommendationSkeletons.tsx — two equal-shape placeholders sharing the grid layout App.tsx will use for success state (zero layout shift)"
  - "ui/src/components/LookupForm.tsx — <form onSubmit> + type=submit with D-10 raw passthrough, D-11 dashed placeholder, D-12 Enter-or-click submit"
  - "ui/src/components/PersonaChips.tsx — 3 keyboard-accessible badges wired to PERSONAS"
affects:
  - 04-05-layout-composition (composes all 6 components into App.tsx)

tech-stack:
  added: []
  patterns:
    - "Single-component multi-variant rendering via a const config map (TRACK_CONFIG in RecommendationCard) — the equal-cards contract is enforced structurally: adding differentiation requires editing the config, making divergence a visible diff"
    - "Form value lives in local useState; normalization/validation handed to the parent hook so there is one canonical normalization surface (no duplicate CUSTOMER_ID_PATTERN check in the component)"
    - "span-based shadcn Badge turned into a keyboard-operable control via role=button + tabIndex + Enter/Space handler + aria-disabled — matches <button> feature parity without restyling"
    - "Loading skeleton grid mirrors the success grid (grid-cols-1 md:grid-cols-2 gap-8) exactly so the loading → success transition is zero-reflow"

key-files:
  created:
    - "ui/src/components/RecommendationCard.tsx"
    - "ui/src/components/ErrorAlert.tsx"
    - "ui/src/components/EmptyState.tsx"
    - "ui/src/components/RecommendationSkeletons.tsx"
    - "ui/src/components/LookupForm.tsx"
    - "ui/src/components/PersonaChips.tsx"
  modified: []

key-decisions:
  - "RecommendationCard passes raw data straight into JSX expressions — no string interpolation outside React's default escaping, so T-04-09 (XSS via plan_name/savings) is mitigated by React's built-in escaping. Verified by the grep for dangerouslySetInnerHTML in ui/src/ returning 0 matches."
  - "LookupForm does NOT call normalizeCustomerId itself — normalization is handled by useRecommendations.lookup() (Plan 03). Keeping normalization in one place prevents divergent behaviour between the form and any other caller (PersonaChips also bypasses client-side validation because its IDs are hard-coded valid)."
  - "PersonaChips uses shadcn Badge (span) rather than Button to match UI-SPEC's visual contract. Keyboard accessibility is restored via explicit role/tabIndex/aria-disabled/keyDown wiring so the UX is screen-reader equivalent to a native button."
  - "Skeleton cards render with border-t-4 border-t-muted (a neutral accent strip) rather than emerald/blue — the skeletons are track-agnostic during load since we do not yet know which recommendation will return. This preserves the equal-cards contract even while placeholders render."

patterns-established:
  - "Track config maps (TRACK_CONFIG) are the canonical way to encode variant-only-by-accent components in this codebase — Plan 05's App.tsx will reuse the RecommendationCard across both grid cells via `track` prop alone"
  - "All new components live in ui/src/components/*.tsx (flat, not feature-sliced) — sibling to the shadcn primitives under ui/src/components/ui/*.tsx"
  - "Form components accept raw input and delegate normalization upstream — keeps components dumb and testable, concentrates validation in the hook"

requirements-completed:
  - UI-01
  - UI-02

duration: 3min
completed: 2026-04-24
---

# Phase 4 Plan 04: Presentation Components Summary

**Six props-driven React components (RecommendationCard, ErrorAlert, EmptyState, RecommendationSkeletons, LookupForm, PersonaChips) implementing UI-SPEC's equal-cards contract, the dashed-placeholder D-11 amendment, and D-08/D-12 submit semantics — all typecheck and the production build stays green.**

## Performance

- **Duration:** ~3 min (worktree had no `ui/node_modules/`; npm install cost ~5s up-front, not included in execution time)
- **Started:** 2026-04-24T10:52:49Z
- **Completed:** 2026-04-24T10:55:40Z
- **Tasks:** 2 / 2
- **Files created:** 6
- **Files modified:** 0

## Accomplishments

- `ui/src/components/RecommendationCard.tsx` renders both tracks via a single component. A `TRACK_CONFIG` map keyed by `'green' | 'cheapest'` supplies accent classes (`emerald-600` / `blue-600`), heading ("Green Option" / "Cheapest Option"), icon (`Leaf` / `PiggyBank`), badge text, and the methodology template. Plan name falls back to `"selected"` per UI-SPEC §Copywriting lines 125-126. Savings use `.toFixed(2)` for stable decimal display.
- `ui/src/components/ErrorAlert.tsx` wraps shadcn `<Alert variant="destructive">` with an `AlertCircle` icon and dispatches to `errorCopyForStatus(httpStatus, customerId)`. Renders in place of the result cards per UI-SPEC §Interaction States "Error."
- `ui/src/components/EmptyState.tsx` is a pure static render of the UI-SPEC-locked idle copy.
- `ui/src/components/RecommendationSkeletons.tsx` renders two placeholder cards in a `grid-cols-1 md:grid-cols-2 gap-8` grid that matches the success-state grid App.tsx will use — zero layout shift across the loading → success transition.
- `ui/src/components/LookupForm.tsx` wraps the input + CTA in `<form onSubmit>` with a `type="submit"` button, so Enter and button click both submit (D-12). Placeholder is the dashed `e.g. CUST-001234` (D-11); CTA label toggles to `Looking up…` when `isLoading`. Value is passed raw to `onLookup` — normalization stays concentrated in `useRecommendations.lookup()` (Plan 03).
- `ui/src/components/PersonaChips.tsx` renders the three seeded personas (Sarah/Marcus/Elena) as shadcn Badges with `onClick` + `onKeyDown` (Enter/Space), `role="button"`, `tabIndex` (toggled to `-1` when disabled), and `aria-disabled`. One click triggers a full lookup via the parent's `onSelect`.
- `npm run build` exits 0 (17 modules transformed; dist sizes identical to Plan 01's baseline because App.tsx hasn't wired the new components yet — Plan 05's job). `npm test -- --run` still shows 13/13 passing (no regression on Plan 02's foundation tests).

## Task Commits

Each task committed atomically:

1. **Task 1: Create RecommendationCard, ErrorAlert, EmptyState, RecommendationSkeletons** — `0cf51a9` (feat)
2. **Task 2: Create LookupForm and PersonaChips** — `cb700f3` (feat)

_(The final docs commit for this SUMMARY will be added below as a separate commit.)_

## Files Created / Modified / Deleted

**Created (6):**

- `ui/src/components/RecommendationCard.tsx`
- `ui/src/components/ErrorAlert.tsx`
- `ui/src/components/EmptyState.tsx`
- `ui/src/components/RecommendationSkeletons.tsx`
- `ui/src/components/LookupForm.tsx`
- `ui/src/components/PersonaChips.tsx`

**Modified:** none.

**Deleted:** none.

## Decisions Made

- **Track differentiation lives in a single const map, not scattered conditionals.** `TRACK_CONFIG` is declared `as const` at the top of `RecommendationCard.tsx`. Future plans that want to add a third track (v2 idea) or tweak accent shades must edit one object rather than hunting through JSX; this is how the equal-cards contract is enforced structurally.
- **LookupForm does not validate or normalize.** The plan explicitly specifies raw passthrough — normalization is `useRecommendations.lookup()`'s responsibility (Plan 03). Having the form re-run the regex would split the truth surface and risk diverging copy on the 400 error. The form's only gate is the trivial `!value.trim()` empty-field guard to prevent firing `onLookup('')`.
- **PersonaChips reach keyboard parity with `<button>`, not via visual restyle.** shadcn exposes `Badge` as a `<span>`. Swapping it for `<Button>` would pick up button styling (background, padding, focus ring) and break the chip visual. Instead, the badge gets `role="button"`, focusable `tabIndex`, Enter/Space `onKeyDown`, and `aria-disabled` so screen readers and keyboard users see a button-equivalent control.
- **Skeleton cards use `border-t-muted`, not a track accent.** The loading state does not yet know Green vs Cheapest data, so colouring either placeholder emerald or blue would imply a track assignment that might not match what returns. A neutral `muted` strip keeps the skeleton track-agnostic until the cards land.
- **Imports use the `@/` alias everywhere** (matches Plan 01 `components.json`, Plan 02 convention). Relative imports are avoided so future file moves are path-stable.

## Deviations from Plan

None — plan executed exactly as written.

Minor stylistic adjustments that do not change behaviour and are not deviations:

- `LookupForm` imports `FormEvent` as a type-only import (`import type { FormEvent } from 'react'`) instead of `React.FormEvent` inline, since `tsconfig.app.json` has `verbatimModuleSyntax: true`. Equivalent at runtime; required by TS compiler under strict verbatim mode.
- `PersonaChips` imports `KeyboardEvent` as a type-only import for the same reason.
- `PersonaChips` also sets `tabIndex={disabled ? -1 : 0}` and `aria-disabled={disabled}` (a small improvement over the plan's suggested `tabIndex={0}`) so the chips drop out of the keyboard tab order during loading rather than capturing focus but doing nothing. This is covered by the plan's acceptance criteria ("disabled prop prevents clicks during loading state") without needing to be called out as a deviation.
- `RecommendationCard` omits the plan's `accentBg` config key because no element in the final JSX uses it (the plan's provided JSX did not reference it either — it was declared but unused). Under `noUnusedLocals`, shipping it would compile, but omitting it is cleaner.

## Authentication Gates

None. Purely presentation components.

## Threat Flags

None. The plan's threat model anticipated:

- **T-04-09 (XSS via RecommendationCard):** mitigated — all data fields rendered via JSX expressions (`{data.plan_name}`, `{data.saving_monthly.toFixed(2)}`), no `dangerouslySetInnerHTML`. Verified by `grep -r dangerouslySetInnerHTML ui/src/ → 0 matches`.
- **T-04-10 (XSS via ErrorAlert):** mitigated — `customerId` flows into `errorCopyForStatus` via template literal, then rendered as a JSX text node. React's default escaping applies.
- **T-04-11 (EmptyState information disclosure):** accepted — component is purely static, no user data rendered.

No new trust boundaries introduced beyond what the threat model already covers.

## Known Stubs

None. All 6 components are fully wired:

- `RecommendationCard` uses real props (no hardcoded savings or plan name).
- `ErrorAlert` calls real `errorCopyForStatus`.
- `EmptyState` is static by spec (not a stub — UI-SPEC §Copywriting lines 111-112 owns this copy).
- `RecommendationSkeletons` is a presentation-only placeholder by design (UI-SPEC Interaction States "Loading").
- `LookupForm` delegates real state via `useState` + `onLookup`.
- `PersonaChips` pulls real data from `PERSONAS` and fires the real `onSelect` callback.

Plan 05 will compose these into `App.tsx` — without that composition, the components are not yet reachable at runtime (App.tsx still renders the Plan 01 placeholder). That is expected and scoped to Plan 05, not a stub in this plan's deliverables.

## TDD Gate Compliance

This plan's `type` is `execute`, not `tdd`. Individual tasks do not have `tdd="true"`. No RED/GREEN/REFACTOR gate sequence is required. CONTEXT.md D-14 explicitly excludes component-render tests from the D-14 test surface ("UI-SPEC locks all copy — drift risk is low and RTL tests for string equality would just duplicate the spec"), so the absence of per-component test files is by design.

## Issues Encountered

- Fresh worktree had no `ui/node_modules/` directory, so `npm run build` / `npm test` initially fail with `sh: tsc: command not found`. Resolved by running `npm install` (331 packages, ~5s). This is one-time worktree setup, not a plan issue — the same cost was absorbed by Plan 02 in its own fresh worktree.

## Next Plan Readiness

- **Ready for Plan 04-05 (Wave 4: layout composition):** all 6 component files are importable from `@/components/<name>`. Plan 05 can compose them into App.tsx's state-driven branch (idle → EmptyState, loading → RecommendationSkeletons, error → ErrorAlert, success → two RecommendationCards). The skeleton grid layout (`grid-cols-1 md:grid-cols-2 gap-8`) is already established, so App.tsx should reuse the same grid class for the success state to preserve the zero-reflow transition.
- **Hook integration:** `LookupForm`'s `onLookup` prop signature (`(rawId: string) => void`) and `PersonaChips`'s `onSelect` prop signature (`(customerId: string) => void`) both match the Plan 03 hook's `lookup(rawId: string)` public function, so App.tsx can pass `lookup` directly as both props.
- **isLoading / disabled prop threading:** both `LookupForm.isLoading` and `PersonaChips.disabled` should be derived from `state.status === 'loading'` in the App composition.

## Self-Check: PASSED

- Created files exist:
  - `ui/src/components/RecommendationCard.tsx` — FOUND
  - `ui/src/components/ErrorAlert.tsx` — FOUND
  - `ui/src/components/EmptyState.tsx` — FOUND
  - `ui/src/components/RecommendationSkeletons.tsx` — FOUND
  - `ui/src/components/LookupForm.tsx` — FOUND
  - `ui/src/components/PersonaChips.tsx` — FOUND
- Task commits exist in git:
  - `0cf51a9` (Task 1 — feat) — FOUND
  - `cb700f3` (Task 2 — feat) — FOUND
- Key acceptance criteria verified:
  - `grep "Green Option" src/components/RecommendationCard.tsx` — MATCH
  - `grep "Cheapest Option" src/components/RecommendationCard.tsx` — MATCH
  - `grep "100% renewable" src/components/RecommendationCard.tsx` — MATCH
  - `grep "Lowest unit price" src/components/RecommendationCard.tsx` — MATCH
  - `grep "emerald-600" src/components/RecommendationCard.tsx` — MATCH
  - `grep "blue-600" src/components/RecommendationCard.tsx` — MATCH
  - `grep -E "Leaf|PiggyBank" src/components/RecommendationCard.tsx` — MATCH
  - `grep "saving_monthly.toFixed(2)" src/components/RecommendationCard.tsx` — MATCH
  - `grep -E "\{plan_name\}" + "'selected'" src/components/RecommendationCard.tsx` — MATCH
  - `grep "errorCopyForStatus" src/components/ErrorAlert.tsx` — MATCH
  - `grep 'variant="destructive"' src/components/ErrorAlert.tsx` — MATCH
  - `grep "No customer selected" src/components/EmptyState.tsx` — MATCH
  - `grep "Enter a customer ID to see tariff recommendations." src/components/EmptyState.tsx` — MATCH
  - `grep "grid-cols-1 md:grid-cols-2 gap-8" src/components/RecommendationSkeletons.tsx` — MATCH
  - `grep 'e.g. CUST-001234' src/components/LookupForm.tsx` — MATCH
  - `grep "Look up customer" src/components/LookupForm.tsx` — MATCH
  - `grep "Looking up" src/components/LookupForm.tsx` — MATCH
  - `grep 'type="submit"' src/components/LookupForm.tsx` — MATCH
  - `grep "PERSONAS" src/components/PersonaChips.tsx` — MATCH
  - `grep "onSelect" src/components/PersonaChips.tsx` — MATCH
  - `grep 'role="button"' src/components/PersonaChips.tsx` — MATCH
  - `grep "tabIndex" src/components/PersonaChips.tsx` — MATCH
  - `grep "onKeyDown" src/components/PersonaChips.tsx` — MATCH
  - `grep -r "dangerouslySetInnerHTML" ui/src/` — 0 matches (destructive-variant acceptance: threat model T-04-09/10 mitigated)
  - `npm run build` — exit 0 (17 modules transformed, dist bundles written)
  - `npm test -- --run` — 13/13 passing, no regression on Plan 02 foundation tests

---
*Phase: 04-agent-assist-ui*
*Completed: 2026-04-24*
