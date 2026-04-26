# Phase 8: UI Integration + Feature Flag + Version Indicator - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Render the `usage_narrative` + `call_script` fields (emitted by the Phase 6 agent, passed through verbatim by the Phase 7 API Lambda) on each of the two `RecommendationCard` tracks (Green, Cheapest) with skeleton-first layout stability. Wire a URL-level kill switch `?narrative=off` that reverts the UI to its v1.0 visual shape without a redeploy. Bake a build-time `v2.0 · <git-sha>` indicator into the bottom-right corner of the UI so operators can verify at demo time which bundle is actually live. Keep `build:mock` emergency-swap path working end-to-end with the extended `TrackInfo` shape. Closes UI-03 (UI half), UI-04 (UI half), UI-06, UI-07, UI-08.

**In scope (Phase 8 only):**
- `ui/src/lib/types.ts` — extend `TrackInfo` with required `usage_narrative: string` and `call_script: string`
- `ui/src/components/RecommendationCard.tsx` — render narrative (italic, muted) between savings grid and methodology; render call_script (bordered quote block, track-accent left border) below methodology
- `ui/src/components/RecommendationSkeletons.tsx` — add skeleton rows matching final narrative + call_script heights for zero layout shift (UI-08)
- Feature flag module (new small module: `ui/src/lib/flags.ts`) — reads `?narrative=off` from `window.location.search` exactly once at module load, exports `NARRATIVE_ENABLED: boolean`; consumed by both `RecommendationCard` and `RecommendationSkeletons` to hide narrative + call_script rows AND their skeleton placeholders when the flag is off
- Version indicator component (new: `ui/src/components/VersionIndicator.tsx`) — renders `v2.0 · <7-char-sha>` bottom-right fixed, muted-foreground, always visible; consumes a `__GIT_SHA__` define
- `vite.config.ts` — add `define` that reads `git rev-parse --short HEAD` via `child_process.execSync` at build time and injects `__GIT_SHA__`; fall back to `"unknown"` if git is unavailable (so CI/build:mock never hard-fail)
- `ui/src/lib/mock/recommendations.ts` — extend all 3 persona fixtures with `usage_narrative` + `call_script` strings copied verbatim from `agent/narrative/fallbacks.py` so the mock dist matches demo-ready copy byte-for-byte
- Vitest additions: `RecommendationCard` renders both narrative rows for Green + Cheapest (2 cases); `?narrative=off` hides both rows and their skeleton placeholders; `RecommendationSkeletons` renders narrative placeholders by default; `VersionIndicator` renders with a mocked `__GIT_SHA__`; a new mock-content-rules test asserts every `MOCK_RECOMMENDATIONS` narrative + script string passes the Phase 6 validator rules (no digit, no `$£€%`, ≤20 words for narrative, ≤22 words for call_script)
- Live smoke closeout: primary `npm run build` against the deployed API URL produces a dist whose `v2.0 · <sha>` corner marker matches the commit being shipped; `build:mock` regenerates a working dist with the extended TrackInfo shape; both cards remain above the fold at 1280×800 with the longest committed fallback strings (visual check, single human observation, documented in SUMMARY)

**Out of scope (Phase 8 does NOT do):**
- `scripts/prewarm.py`, `scripts/demo-keepalive.sh`, end-to-end narrative eval harness — Phase 9 (DEMO-03 tooling half + DEMO-05)
- Freeze artefacts (`FREEZE-MANIFEST.md`, stack policies, `demo-v2.0` tag, rollback drill) — Phase 10
- Any change to `agent/`, `api_lambda/`, or CDK infrastructure — Phase 6/7 locked. This is a UI-layer-only phase.
- Presenter tooltip (alt-click raw LLM + verdict) — considered across Phase 6/7 context, explicitly deferred. Would require `_narrative_source` to reach the UI, which Phase 7 D-06 strips. Out of scope again here.
- Streaming narrative, regenerate-button, visual A/B — locked out of scope for v2.0 at requirements stage.
- Responsive / mobile layout — desktop 1280px only (v1.0 carry-forward).
- Provisioning / CI wiring for a separate "demo" deployment channel — not needed; single live endpoint.
- Zod or other runtime response validation at the hook layer — Phase 6 Pydantic validator is the sole content guarantor; adding a second gate on the UI side is over-engineering for the demo window.

**Success criteria (from ROADMAP.md):**
1. On every persona lookup, each recommendation card renders one usage-narrative row and one call-script row with no layout shift (skeleton → content transition matches the final row heights).
2. Both cards remain above the fold at 1280×800 when the narratives are at maximum generated length, validated against the longest committed fallback strings.
3. Appending `?narrative=off` to the URL hides both narrative rows without any redeploy and without collapsing the card layout.
4. A `v2.0 · <git-sha>` indicator is visible in a corner of the UI and matches the SHA of the deployed build.
5. `build:mock` regenerates a dist that still renders correctly with the extended `TrackInfo` shape, preserving the <10s emergency swap path.

</domain>

<decisions>
## Implementation Decisions

### Card Layout + Visual Treatment (UI-03 + UI-04 UI half)

- **D-01:** Card row order is **Plan name → Savings grid (monthly / annual) → Usage narrative → Methodology line → Call script**. Narrative sits *between* the savings grid and the methodology line — tight against the numbers it describes. The methodology line ("Based on your 12-month kWh usage at the {plan_name} rate …") stays as the audit trail and sits *below* the narrative. Call script is the last visible block on the card. This matches ARCHITECTURE.md §"Where It Renders on the Card" — narrative directly under numbers — while preserving the Phase 4 methodology line as the final piece of numeric context.

- **D-02:** Narrative is rendered as an **italic, `text-muted-foreground`, `text-sm` paragraph**. No label, no section header, no quote marks, no divider line. Reads as subdued analyst context — the visual peer of the methodology line below it. Third-person descriptive voice per Phase 6 UI-04 schema.

- **D-03:** Call script is rendered as a **bordered quote block with a track-colored left border** (`border-l-4 border-l-emerald-600` on Green, `border-l-4 border-l-blue-600` on Cheapest), `pl-4 py-2`, slightly larger than narrative (`text-base`), quoted with `❝ … ❞` (U+275D / U+275E) via CSS `::before`/`::after` or inline. Second-person voice per Phase 6 UI-03 schema, read-aloud by the call-centre agent — visual distinction reinforces "read this verbatim." Uses the same track-accent color family as the top border so the two accents stay coordinated.

- **D-04:** Narrative and call_script fields are always present on the response and always rendered (no empty-state handling). Phase 6 D-02 / D-04 guarantees non-empty, validator-passing strings via per-field fallback. The UI never needs a "narrative missing" branch.

- **D-05:** Card height budget — with the longest committed Phase 6 fallback strings at 1280×800, both cards must remain above the fold. The fallback strings are demo-ready (≤20 words narrative / ≤22 words call_script, per Phase 6 D-06) so at `text-sm` / `text-base` they fit in ~60px for narrative + ~80px for call_script when wrapped. v1.0 card ≈ 280px. v2.0 card ≈ 420–440px. 1280×800 usable vertical is ~680px with browser chrome; two cards side-by-side fit comfortably. Visual confirmation is a human UAT step in the closeout; no automated layout assertion (jsdom can't measure real heights reliably).

### Skeleton-First Layout Stability (UI-08)

- **D-06:** `RecommendationSkeletons` is extended in-place — new placeholder rows are added for the narrative and call_script in the same grid position as the final rendered rows. Skeleton shape:
  - Narrative placeholder: one `Skeleton h-4 w-full` above a `Skeleton h-4 w-4/5` (2 lines matching typical narrative wrap).
  - Call script placeholder: one `Skeleton h-5 w-full` above a `Skeleton h-5 w-5/6` above a `Skeleton h-5 w-3/5`, wrapped in the same `border-l-4 border-l-muted pl-4` shell used by the final render (shell-matched placeholder). 3 lines matching typical call_script wrap.
  The heights + widths are picked to match the final rendered rows at `text-sm` / `text-base` within ±4px so the transition is effectively shift-free.

- **D-07:** No extraction of a `NarrativeSkeleton` sub-component. The skeleton tree stays inline in `RecommendationSkeletons` to keep the "skeleton mirrors the final card shape" rule auditable in a single file — same principle that already guides the existing Phase 4 skeleton. Reusability is not worth the indirection for two new placeholder blocks used in exactly one place.

- **D-08:** No `getBoundingClientRect`-based height-match assertion in vitest. jsdom does not implement layout, so measured heights are synthetic and give false confidence. Real-height validation is human visual UAT at the closeout gate (D-19). Playwright visual regression is explicitly rejected below (D-21).

### Feature Flag `?narrative=off` (UI-06)

- **D-09:** Feature flag is read **exactly once at module load** via a new small module `ui/src/lib/flags.ts`. It exports a module-level const `NARRATIVE_ENABLED: boolean` derived from `new URLSearchParams(window.location.search).get('narrative') !== 'off'`. No React state, no context provider, no hook. Consumers (`RecommendationCard`, `RecommendationSkeletons`) import the const directly. Evaluated once per page load — demo-day usage is "presenter reloads with `?narrative=off`", never toggled mid-session.

- **D-10:** When `NARRATIVE_ENABLED === false`, both the narrative row and the call_script row are suppressed in `RecommendationCard`, AND their matching skeleton placeholder rows are suppressed in `RecommendationSkeletons`. Card height in both loading and success states visibly matches the v1.0 shape when the flag is on. This is the primary runtime rollback lever — its contract is "UI is byte-equivalent to v1.0 when flag is active."

- **D-11:** No persistence — no `sessionStorage`, no `localStorage`. URL is the only source of truth. Refreshing without the query param turns narrative back on. Re-queries within the same session preserve the flag naturally because `window.location.search` doesn't change across React re-renders. Keeps the freeze surface minimal (no extra storage keys in the freeze manifest) and keeps the operator contract auditable ("what you see in the URL is what's active").

- **D-12:** Flag value is **not** exposed via a React hook or prop chain. Module-level const is imported by consumers. Rationale: testability is preserved (vitest mocks `window.location` before module import via `vi.hoisted` / per-test setup) and there's zero runtime prop plumbing. App.tsx does not pass a `narrativeEnabled` prop to `RecommendationCard` — each consumer reads the flag from the same source.

- **D-13:** The flag is read against the *exact* token `"off"` (case-sensitive). Any other value (`?narrative=0`, `?narrative=false`, absent) means narrative is on. Rationale: operator mnemonic is the literal word "off"; permissive parsing adds ambiguity and test combinatorics for no benefit.

### Version Indicator (UI-07)

- **D-14:** Version indicator renders in a **bottom-right fixed corner** via `position: fixed; bottom: 8px; right: 8px;` (Tailwind `fixed bottom-2 right-2`). Small `text-xs`, `text-muted-foreground`, `opacity-60` to stay subdued. Always visible, never hidden behind the cards (which live in a centered `max-w-4xl` column at the top of the page). Bottom-right chosen over top-right because DevTools docked-right at 1280px can collide with the top.

- **D-15:** Git SHA is injected at build time via **Vite `define`** in `vite.config.ts`. The config calls `require('child_process').execSync('git rev-parse --short HEAD').toString().trim()` inside a try/catch; on failure (no git, detached tree, CI without git), substitutes `"unknown"`. The define key is `__GIT_SHA__` (double-underscore-prefixed is Vite's documented convention for globals). Embedded at build time → zero runtime cost, deterministic per build, matches `build:mock` reproducibility (both `build` and `build:mock` get the same SHA because they run against the same tree). TypeScript declaration for `__GIT_SHA__` goes in `ui/src/vite-env.d.ts` (existing) so the global is typed.

- **D-16:** Indicator text format is literal `v2.0 · <7-char-sha>` using U+00B7 MIDDLE DOT as the separator. Matches ROADMAP.md Success Criterion 4 verbatim and the middle-dot convention established by Phase 4's persona label format (`CUST-NNN · <profile>`). No build timestamp — one build-time define only.

- **D-17:** New component `ui/src/components/VersionIndicator.tsx` owns the element. `App.tsx` renders `<VersionIndicator />` once at the root of the `<div className="min-h-screen …">`, outside the `<main>` so it doesn't participate in card layout. Component is trivial (one span, one className, one interpolated `__GIT_SHA__`). No props, no tests beyond "renders with mocked global."

### TrackInfo TS Type + Mock Fixture Content

- **D-18:** `TrackInfo` is extended with two **required** string fields: `usage_narrative: string` and `call_script: string`. Matches the post–Phase 6/7 backend contract exactly — agent always returns non-empty values (Phase 6 fallback guarantees), Lambda passes through verbatim (Phase 7 D-08). Required (not optional) so TypeScript catches any test / mock / component call that forgets them. No Zod or runtime validation in the hook — Phase 6 Pydantic is the sole content guarantor.

- **D-19:** Mock fixture copy is **copied verbatim from `agent/narrative/fallbacks.py`** (Phase 6 committed fallbacks). All 6 strings (3 personas × 2 tracks × {usage_narrative, call_script}) are pasted into `ui/src/lib/mock/recommendations.ts` as string literals. This keeps the mock dist indistinguishable from the live dist for any seeded persona and guarantees the mock survives the `build:mock` emergency-swap use case (<10s swap is v1.0 D-07 carry-forward). Rule: **if `agent/narrative/fallbacks.py` changes, the TS mock MUST be updated in the same commit** — same discipline as the existing $30/$55 numbers (Phase 4 comment in `recommendations.ts` already states this pattern).

- **D-20:** No build-time sync script (no `scripts/sync-mock-narratives.js`). Python↔TS bridge for 6 strings is over-engineered. Manual copy-paste with the in-file comment documenting the rule is sufficient; discipline carries the contract.

### Test Coverage

- **D-21:** Vitest suite additions (no new test dependencies):
  - `RecommendationCard.test.tsx` (new): renders Green track with narrative + call_script, renders Cheapest track likewise, asserts narrative appears between savings-grid and methodology in DOM order, asserts call_script appears below methodology, asserts track-accent border class applied to the call_script quote block.
  - `RecommendationCard.test.tsx` with `?narrative=off`: vitest-mock `window.location.search` to `?narrative=off`, re-import `flags.ts` (or use `vi.resetModules()` + dynamic import), render card, assert both narrative and call_script nodes are absent from the tree.
  - `RecommendationSkeletons.test.tsx` (new): default render includes narrative + call_script placeholder rows; `?narrative=off` mode asserts they are absent.
  - `VersionIndicator.test.tsx` (new): with `globalThis.__GIT_SHA__ = "abc1234"`, asserts element renders the literal `v2.0 · abc1234`.
  - `recommendations.test.ts` or `mock/recommendations.test.ts` (new): iterates every `TrackInfo` in `MOCK_RECOMMENDATIONS` and asserts each `usage_narrative` and `call_script` (a) contains no digit, no `$`, no `£`, no `€`, no `%`, (b) word count ≤20 for narrative, ≤22 for call_script. This mirrors the Phase 6 `test_fallbacks_pass_validator` test — catches mock-authoring drift at the UI layer.
  - `personas.test.ts` is NOT modified — personas are unchanged.
  - `useRecommendations.test.ts` is NOT modified — the hook's contract is the same shape (`RecommendationResponse`); the extended `TrackInfo` flows through without hook changes.
  - Full `npm test` must stay green. No existing Phase 4 test is deleted or rewritten.

- **D-22:** No `getBoundingClientRect` / layout-shift assertion (D-08). No Playwright visual regression — adding Playwright expands the freeze surface and package.json deps for a single-shot demo. Layout stability is validated at the human UAT closeout gate.

### Live Smoke + Closeout Gate

- **D-23:** Phase 8 closeout gate (documented in plan SUMMARY, NOT shipped as pytest):
  1. `npm test` green (Phase 4 + Phase 8 vitest suites + mock validator test).
  2. `npm run build` completes; inspect `dist/assets/*.js` for the embedded SHA string (or open the built dist in preview and verify corner marker visually).
  3. `npm run build:mock` completes; inspect `dist-mock/` likewise; mock preview renders all 3 personas with narrative + call_script visible and above the fold.
  4. Against the live API (`https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/`), exercise all 3 personas in the browser at 1280×800 and visually confirm: (a) narrative + call_script render below savings / above methodology (narrative) and at card bottom (script); (b) both cards above the fold at maximum rendered length; (c) bottom-right corner shows `v2.0 · <sha>` matching the built commit SHA; (d) `?narrative=off` URL hides both narrative rows AND the skeleton placeholders; (e) without the flag, loading → success is visibly shift-free.
  5. Capture the 1280×800 screenshots (3 personas × {on, off, loading} = 9) into `08-SAMPLES.md` as the evidence artefact.
  Phase 8 does NOT close until D-23 passes. Phase 9 (prewarm tooling + eval harness) and Phase 10 (freeze) both depend on this visual contract holding.

### Claude's Discretion

- **Exact vertical spacing between narrative, methodology, and call_script rows.** D-01 fixes the order; precise `space-y-*` / `mt-*` values are planner/executor discretion. Default to the existing Phase 4 `space-y-4` pattern on `CardContent` and add targeted `mt-4` only where visual grouping demands it. Visual tightening is acceptable during the D-23 human UAT.
- **Whether to introduce a `TrackAccentBorder` utility or keep the `border-l-4 border-l-emerald-600` / `border-l-blue-600` inline in RecommendationCard.** Planner decides; recommend inline to match the existing `TRACK_CONFIG.accentBorder` pattern at the top of `RecommendationCard.tsx`.
- **Extracting the flag read into `flags.ts` vs. inlining it.** D-09 commits to a dedicated module for testability (mock `window.location` + reset modules); planner confirms. The module is one line: `export const NARRATIVE_ENABLED = new URLSearchParams(window.location.search).get('narrative') !== 'off';`.
- **`__GIT_SHA__` TypeScript declaration location.** `ui/src/vite-env.d.ts` (existing file, owned by Vite template) is the natural home. Planner may alternately create `ui/src/build-info.d.ts` if declutter is preferred; recommend vite-env.d.ts to keep build-time globals in one place.
- **Visual treatment of the `❝ … ❞` quote marks on the call_script.** Inline text content vs. CSS pseudo-elements vs. lucide `Quote` icon. Planner decides; recommend inline text (U+275D / U+275E) to keep the render server-renderable with zero CSS state — matches the "stable DOM" feature-flag contract (flag off = v1.0 shape, no leftover quote-mark CSS).
- **Whether `flags.ts` also exports a `GIT_SHA` re-export of `__GIT_SHA__`.** Minor convenience so `VersionIndicator` doesn't reference the global directly in TS; recommend no (keep `flags.ts` narrowly scoped to the narrative flag).
- **Opacity of the version indicator.** D-14 lands at `opacity-60` as a starting point; planner may tighten to `opacity-50` if it reads too prominent in live rehearsal. Must remain legible from presenter's laptop at demo time.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.0 Requirements + Roadmap

- `.planning/REQUIREMENTS.md` — §"Agent-Assist LLM Narrative (UI)" for UI-03 (UI half), UI-04 (UI half), UI-06 (feature flag), UI-07 (version indicator), UI-08 (skeleton-first + above-the-fold). §"Key Decisions Locked at Requirements Stage" for rollback mechanism (feature flag is the *primary runtime rollback lever*; `demo-v1.0` + `build:mock` are the outer safety nets).
- `.planning/ROADMAP.md` §"Phase 8: UI Integration + Feature Flag + Version Indicator" — 5 success criteria. All 5 must be TRUE before Phase 10 (freeze + drill) closes; Phase 9 (prewarm tooling) is non-blocking and parallel.
- `.planning/PROJECT.md` — Core value, constraints, "Recommendation design" invariant (Green + Cheapest surfaced together, neither ranked — equal-cards contract remains load-bearing).
- `.planning/STATE.md` — v2.0 blockers/concerns (UI-01 + UI-02 must stay satisfied with narratives at max generated length).

### Phase 6 + Phase 7 Artefacts (upstream contracts this phase consumes)

- `.planning/phases/06-agent-narrative-guardrail/06-CONTEXT.md` — **D-02 / D-04 are load-bearing**: narrative fields are always non-empty (per-field fallback on validator failure), so the UI never handles a missing-field state. **D-06 is the authority on the committed fallback strings** that Phase 8's mock fixture copies verbatim (D-19).
- `agent/narrative/fallbacks.py` — the 6 canonical fallback strings Phase 8 mirrors into `ui/src/lib/mock/recommendations.ts` byte-for-byte.
- `.planning/phases/07-api-pass-through-pre-warm-route/07-CONTEXT.md` — **D-06 / D-08 are load-bearing**: `_narrative_source` marker is stripped by the API Lambda and never reaches the UI; narrative fields flow through byte-identically. Phase 8 trusts the wire shape exactly as Phase 7 defines it.
- `.planning/phases/07-api-pass-through-pre-warm-route/07-SUMMARY.md` — live smoke evidence: API passes extended TrackInfo end-to-end, `_narrative_source` absent from client-visible body.

### v2.0 Research

- `.planning/research/ARCHITECTURE.md` §"UI-03 / UI-04 — Generation Strategy" → §"Where It Renders on the Card" — card anatomy mock that D-01/D-02/D-03 build on.
- `.planning/research/ARCHITECTURE.md` §"Latency Budget — Does UI-02 Survive v2.0?" — skeleton → content transition budget; UI-02 (<3s) is a Phase 9/T-24h concern but the Phase 8 skeleton contract protects the perceived-latency half of it.
- `.planning/research/ARCHITECTURE.md` §"Anti-Patterns" AP-6 — length caps consistent across Pydantic / TS / CSS. Phase 8 lands the TS half (required string type, mock-content-rules test asserts ≤ word caps).
- `.planning/research/ARCHITECTURE.md` §"Phase 2.3 — UI Integration" — phase-level task breakdown matching this phase.
- `.planning/research/FEATURES.md` §"Table Stakes (v2.0)" — Skeleton shimmer on narrative slots, deterministic fallback string per card, output validator in the UI layer (mock-rules vitest delivers the UI half). §"Differentiators" — "narrative-only feature flag (runtime)" maps to UI-06 / D-09–D-13. §"Anti-Features" — rejects streaming narrative, regenerate button, provisioned concurrency on the Lambda (out of Phase 8 scope anyway).
- `.planning/research/PITFALLS.md` — AP-6 narrative length drift (same as ARCHITECTURE AP-6); AP-4 freezing only source not AWS state (Phase 10 concern; Phase 8 is UI only).

### v1.0 Carry-Forward (the stack Phase 8 extends)

- `ui/src/lib/types.ts` — **primary file modified**. `TrackInfo` gains two required string fields (D-18).
- `ui/src/lib/mock/recommendations.ts` — **primary file modified**. Extended with 6 narrative strings copied verbatim from `agent/narrative/fallbacks.py` (D-19).
- `ui/src/components/RecommendationCard.tsx` — **primary file modified**. Add narrative row (D-02) between savings grid and methodology; add call_script block (D-03) after methodology; read `NARRATIVE_ENABLED` from `flags.ts` (D-12) to suppress both when flag is off.
- `ui/src/components/RecommendationSkeletons.tsx` — **primary file modified**. Add narrative + call_script placeholder rows (D-06); consume `NARRATIVE_ENABLED` to suppress them when flag is off (D-10).
- `ui/src/components/VersionIndicator.tsx` — **new file**. Bottom-right fixed corner, renders `v2.0 · <__GIT_SHA__>` (D-14 / D-16 / D-17).
- `ui/src/lib/flags.ts` — **new file**. Single exported const `NARRATIVE_ENABLED` read once at module load from `window.location.search` (D-09).
- `ui/src/vite-env.d.ts` — **augmented**. Declares `__GIT_SHA__: string` as a global for TypeScript.
- `ui/src/App.tsx` — **minor edit**. Renders `<VersionIndicator />` once at the root of `<div className="min-h-screen …">`, outside `<main>` (D-17).
- `ui/vite.config.ts` — **primary file modified**. Adds `define: { __GIT_SHA__: JSON.stringify(gitSha) }` where `gitSha` comes from `execSync('git rev-parse --short HEAD')` inside a try/catch that falls back to `"unknown"` (D-15).
- `ui/package.json` — **unchanged**. No new deps. `build` and `build:mock` scripts unchanged (the SHA injection happens in vite.config.ts, which both scripts share).
- `ui/src/hooks/useRecommendations.ts` — **unchanged**. The hook consumes `RecommendationResponse` which points at the extended `TrackInfo` automatically. D-21 explicitly does not modify the hook tests.
- `ui/src/personas.ts` — **unchanged**. Personas are unaffected by narrative.
- `ui/src/components/ui/skeleton.tsx` — **unchanged**. Reused as-is for the new placeholder rows.
- `ui/src/test-setup.ts` — **unchanged** unless planner decides module-resetting for `flags.ts` testing needs a shared helper there.

### v1.0 Phase Context (for convention carry-forward)

- `.planning/milestones/v1.0-phases/04-agent-assist-ui/04-CONTEXT.md` — Phase 4 decisions: D-01 (native fetch, no data library), D-03 (mock fallback when `VITE_API_URL` unset), D-08 (persona chips middle-dot label convention Phase 8 mirrors for the version indicator format), D-12 (LookupForm submit flow). Phase 8 preserves all of these.
- `.planning/milestones/v1.0-phases/04-agent-assist-ui/` — existing vitest patterns for `RecommendationCard.test.tsx` (not present in v1.0), `useRecommendations.test.ts`, `validate.test.ts`, `personas.test.ts`. Phase 8 adds new test files in the same directory conventions (test adjacent to source).
- `.planning/milestones/v1.0-phases/05-demo-hardening/` — v1.0 D-07 (`build:mock` <10s emergency swap); Phase 8 preserves this (D-19, D-23 step 3).

### External / upstream docs

- **Vite `define` docs** — `https://vite.dev/config/shared-options.html#define` — `__GIT_SHA__` injection semantics. Value must be `JSON.stringify(actualString)` (not the raw string) so Vite emits a valid JS literal.
- **Vite `child_process.execSync` pattern at config time** — standard Node `require('child_process')`. Verify `execSync` output encoding default (Buffer in Node ≥14, `.toString().trim()` is the idiomatic pattern).
- **Tailwind `fixed bottom-2 right-2` + `z-index`** — default Tailwind `fixed` has no z-index; a `z-50` class is needed to guarantee the corner marker sits above any future modal/toast. Planner verifies against current Tailwind v4 config.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `ui/src/components/ui/card.tsx` (shadcn/ui Card, CardHeader, CardContent, CardTitle) — reused as-is. No new card primitive.
- `ui/src/components/ui/skeleton.tsx` (shadcn Skeleton) — reused as-is for the new narrative + call_script placeholders.
- `ui/src/components/ui/badge.tsx` — reused for the existing track badge; no change needed for narrative.
- `ui/src/components/RecommendationCard.tsx::TRACK_CONFIG` — the existing `{ heading, badge, icon, accentBorder, accentText, methodologyTemplate }` map. Phase 8 adds no new keys here; the call_script border color is derived from `accentText` (extract the emerald/blue color token) or inlined via track-conditional ternary. Planner decides.
- `ui/src/components/RecommendationSkeletons.tsx` — existing skeleton tree that already maps to the card shape 1:1. Phase 8 adds rows in the same pattern (Skeleton + spacing), not a new component.
- `ui/src/lib/mock/recommendations.ts` — existing persona-keyed fixture. Extended in place with the 6 narrative strings.
- `ui/src/hooks/useRecommendations.ts` — unchanged. Already parses the response as `RecommendationResponse` → extended `TrackInfo`.
- `ui/src/App.tsx` — adds one new component render (`<VersionIndicator />`) outside `<main>`; no other change.
- `ui/vite.config.ts` — existing `defineConfig` — Phase 8 adds a `define` entry. Existing `alias`, `plugins`, `test` config unchanged.
- `ui/src/test-setup.ts` — existing vitest + `@testing-library/jest-dom` setup. New tests follow the same pattern (no new setup file needed).

### Established Patterns

- **Snake-case field names on the wire contract, mirrored in TS** (Phase 4 convention in `types.ts` comment). Phase 8 preserves this: `usage_narrative`, `call_script` — NOT camelCased.
- **Single file per component, colocated with tests.** Phase 4 pattern: `personas.ts` + `personas.test.ts`, `validate.ts` + `validate.test.ts`, etc. Phase 8 follows — `VersionIndicator.tsx` + `VersionIndicator.test.tsx` in `components/`, `flags.ts` + `flags.test.ts` in `lib/`.
- **Track-agnostic component, parent owns ordering** (Phase 4 RecommendationCard convention). Phase 8 preserves this: narrative + call_script render inside the same track-agnostic component; only their content differs between Green and Cheapest (via the data prop, not a track branch).
- **Equal-cards contract is load-bearing for REC-03** (Phase 4 D-locked). Phase 8 does not introduce any new visual divergence between Green and Cheapest beyond what's already established (accent color, heading, icon, badge, methodology template). Narrative + call_script content differs by data (per track) but the *visual treatment* is identical between tracks.
- **Module-level init for build-time constants.** `flags.ts::NARRATIVE_ENABLED` and the `__GIT_SHA__` global both follow this pattern — evaluated once, consumed as a const.
- **Mock-fixture comment documents the sync rule.** Existing `recommendations.ts` comment explicitly says "If the backend savings formula changes, update both this map AND the Python fixtures in the same commit." Phase 8 extends this rule to cover `agent/narrative/fallbacks.py` synchronisation (D-19).
- **Vitest + jsdom for component tests** — `environment: 'jsdom'` already set in `vite.config.ts`. Real layout is NOT tested (D-08).
- **D-07 from v1.0: don't commit `ui/dist/`.** Phase 8 does NOT commit built artefacts; the `__GIT_SHA__` define makes every build deterministic *from a tree*, but the built dist is still regenerated by `npm run build`, not committed.

### Integration Points

- **Upstream (Phase 6 agent):** `green.usage_narrative`, `green.call_script`, `cheapest.usage_narrative`, `cheapest.call_script` — non-empty strings, validator-passing. UI trusts them verbatim.
- **Upstream (Phase 7 API Lambda):** same shape, stripped of `_narrative_source`. UI trusts the wire body as `RecommendationResponse`.
- **Downstream (Phase 9 prewarm / eval):** none — Phase 9 operates against the live endpoint and does not touch the UI.
- **Downstream (Phase 10 freeze):** `FREEZE-MANIFEST.md` will capture SHA-256 of `dist/` and `dist-mock/` bundles. Both bundles include the embedded `__GIT_SHA__` at build time. DEMO-06 rollback drill exercises (a) `?narrative=off` flag working live and (b) `build:mock` regenerating a working dist with the extended TrackInfo shape — Phase 8 D-10 and D-19 both directly satisfy these.
- **Build:mock reproducibility:** `build:mock` runs with `VITE_API_URL=`, which triggers the mock branch in `useRecommendations` (Phase 4 D-03). With the extended mock fixture (D-19), the mock dist surfaces the same narrative + call_script strings that Phase 6 fallbacks emit — indistinguishable for the demo personas. This is the <10s emergency UI swap path (Phase 5 D-07 / v1.0 carry-forward), preserved intact through v2.0.
- **No AWS change** — Phase 8 is 100% UI-layer. No IAM, no CDK, no Lambda, no API Gateway, no agent container, no DynamoDB.

</code_context>

<specifics>
## Specific Ideas

- **The skeleton → success transition is the UI-08 contract.** The only way to validate it reliably is visual UAT at 1280×800 with the longest committed fallback strings (D-23 step 4e). jsdom and vitest cannot measure real layout shift; Playwright could but is explicitly rejected to keep the freeze surface small. Acceptance is a human eyeball check documented in `08-SAMPLES.md` screenshots.
- **The mock-content-rules vitest (D-21 last bullet) is the UI-layer mirror of Phase 6's `test_fallbacks_pass_validator`.** It's a small, high-value, no-new-deps safeguard against an editor pasting a `$` or a digit into the fixture during rehearsal. Worth the one test.
- **`?narrative=off` must suppress the skeleton too.** If it only hides the rendered rows, the loading state is still v2.0-shaped and the transition collapses when narrative vanishes. The whole point of the flag is "UI looks like v1.0 when the narrative path is suspect" — and v1.0 has no narrative rows *anywhere*, loading or success. D-10 is non-negotiable.
- **Git SHA `"unknown"` fallback is demo-critical.** If a rehearsal build runs in an environment without git (unlikely but possible on a locked-down CI box), the indicator showing `v2.0 · unknown` is strictly better than a build failure. Operators can spot "unknown" and re-run locally.
- **The version indicator exists specifically to defend against stale-bundle risk.** At demo time, the presenter can check the corner marker against the commit they expect, in the browser, without opening DevTools or curling a /version endpoint. It is a *live in-browser diagnostic*. Hover-only or debug-flag-gated variants (rejected in D-14) defeat that purpose.
- **Both `build` and `build:mock` must emit the same `__GIT_SHA__`.** They share `vite.config.ts` so this is automatic — the define is evaluated at config load, not per-script. Verify by running both and inspecting the output bundle for the same SHA string.
- **Do not regress v1.0 tests.** `npm test` full suite must stay green. v1.0 Phase 4 tests (`personas.test.ts`, `validate.test.ts`, `useRecommendations.test.ts`) are untouched.
- **The extended `TrackInfo` type is a single-commit change.** TS, mock fixture, and the tests that assert on the shape all land together. Partial application would fail type-check.

</specifics>

<deferred>
## Deferred Ideas

- **Presenter tooltip (alt-click reveals raw LLM + verdict).** FEATURES.md should-ship, Phase 6 / Phase 7 deferred. Would require `_narrative_source` to survive the API Lambda (contradicts Phase 7 D-06). Not Phase 8 scope. If revived, would need a debug-only endpoint or environment toggle that preserves the marker.
- **Playwright visual regression against 1280×800 card snapshots.** Rejected in D-21 / D-22 — adds Playwright to the stack and freeze surface for a single-shot demo. Reconsider only if demo cadence extends to multiple presentations.
- **`getBoundingClientRect` skeleton-to-card height match assertion in vitest.** Rejected in D-08 — jsdom layout is synthetic. Real layout validated at human UAT.
- **Streaming narrative render (token-by-token).** Locked OUT OF SCOPE for v2.0 at requirements stage. Card renders narrative all-at-once after fetch completes. Reconsider only if post-demo feedback elevates streaming as a must-have.
- **Regenerate-narrative button.** Locked OUT OF SCOPE at requirements stage. Demo trap — no way back from a worse retry on stage.
- **LLM narrative in non-English locales.** Out of scope — v2.0 is English-only. Desktop 1280px English-only call centre context remains the v1.0/v2.0 constraint.
- **Cache narrative per persona to guarantee identical output across rehearsals.** FEATURES.md differentiator — "pre-computed narrative cache for demo personas." Currently satisfied structurally: Phase 6 fallback path is deterministic, and the mock dist serves committed fallbacks. Live-stack re-rolls on every lookup; variance tolerated because the validator + fallbacks bound the output space. Reconsider at T-24h rehearsal if variance is perceived as a risk.
- **Second URL flag to toggle the version indicator off.** Considered in D-14 visibility options; rejected. The indicator is a permanent build-marker by design.
- **localStorage/sessionStorage for the narrative flag.** Rejected in D-11 — URL-only is the simplest auditable contract.
- **Zod or runtime response validation in `useRecommendations`.** Rejected in D-18 — Phase 6 Pydantic is the sole content guarantor; a second validator on the client adds surface without value for a demo with a committed response contract.
- **Extracting `NarrativeSkeleton` into its own component.** Rejected in D-07 — inline keeps the skeleton-mirrors-card rule auditable in one file.
- **Auto-sync `agent/narrative/fallbacks.py` → `ui/src/lib/mock/recommendations.ts` via build script.** Rejected in D-20 — 6 strings, manual discipline + in-file comment is sufficient.
- **Build timestamp in the version indicator.** Rejected in D-16 — one build-time define is enough; the SHA fully identifies the build.
- **CloudWatch alarm on "UI failed to render narrative" (client-side error telemetry).** v3.0 production hardening; demo is single-shot. No client-side telemetry beyond what the hook already has (none).
- **Separate `/debug` route that shows raw agent response.** Scope creep; not needed for presenter verification (corner marker covers "which bundle" and DevTools covers "what the API returned"). Reconsider if post-demo debrief demands it.

</deferred>

---

*Phase: 08-ui-integration-feature-flag-version-indicator*
*Context gathered: 2026-04-26*
