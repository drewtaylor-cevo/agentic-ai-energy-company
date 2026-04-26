# Phase 8: UI Integration + Feature Flag + Version Indicator - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 08-ui-integration-feature-flag-version-indicator
**Areas discussed:** Card layout + skeleton shape, Feature flag wiring (?narrative=off), Version indicator (UI-07), Types + mock fixture + test posture

---

## Card layout + skeleton shape

### Q1: Where should the usage_narrative and call_script rows sit inside RecommendationCard?

| Option | Description | Selected |
|--------|-------------|----------|
| Below methodology line | Plan → savings → methodology → narrative → call_script. Narrative + script at bottom, methodology preserved as context for numbers. | |
| Between savings and methodology | Narrative directly under numbers (ARCHITECTURE.md mock), methodology stays as audit trail, call_script at bottom. | ✓ |
| Methodology replaced by narrative, script last | Drop the generic methodology line; narrative *is* the methodology for this customer. | |

**User's choice:** Between savings and methodology
**Notes:** Matches ARCHITECTURE.md §"Where It Renders" mock — narrative tight against numbers; methodology retained as audit trail.

### Q2: How should narrative + call_script visually distinguish from other card rows?

| Option | Description | Selected |
|--------|-------------|----------|
| Italic muted narrative + bordered quote script | Narrative italic text-muted-foreground; call_script bordered quote block with ❝ ❞ and track-color left border. | ✓ |
| Plain paragraphs with section labels | Both as plain paragraphs with small-caps section labels. | |
| Labeled rows matching existing pattern | Match "Recommended plan" / "Monthly saving" row style exactly. | |

**User's choice:** Italic muted narrative + bordered quote script
**Notes:** Script visual weight reinforces "read this verbatim" affordance.

### Q3: How should the skeleton state handle the new narrative rows?

| Option | Description | Selected |
|--------|-------------|----------|
| Extended skeleton matching final heights | Add narrative + call_script skeleton lines to RecommendationSkeletons matching final row heights for zero layout shift. | ✓ |
| Conservative single-line skeleton each | One Skeleton per new row sized for typical short content. | |
| No skeleton for narrative rows | Don't modify skeleton — explicit UI-08 regression. | |

**User's choice:** Extended skeleton matching final heights
**Notes:** Hard-enforces UI-08. Two-line narrative placeholder + three-line call_script placeholder with matching border shell.

---

## Feature flag wiring (?narrative=off)

### Q4: Where should ?narrative=off be read in the UI?

| Option | Description | Selected |
|--------|-------------|----------|
| Module-level const at app boot | Read URL once via URLSearchParams at module load, export NARRATIVE_ENABLED const. | ✓ |
| Read in App.tsx, passed as prop | App reads URL once at mount, props down to consumers. | |
| Read inside RecommendationCard directly | Each card reads URL at render time. | |

**User's choice:** Module-level const at app boot
**Notes:** No React state, no context provider. Single source of truth via `ui/src/lib/flags.ts`.

### Q5: What should ?narrative=off hide?

| Option | Description | Selected |
|--------|-------------|----------|
| Both narrative rows AND matching skeleton rows | Card shape matches v1.0 in both loading and success states when flag is on. | ✓ |
| Only the narrative rows in success state | Skeleton stays v2.0-shaped; only rendered rows hide. | |
| Hide rows AND suppress fetch-time differences | Same as option 1 plus any residual v2.0 state (nothing material). | |

**User's choice:** Both narrative rows AND matching skeleton rows
**Notes:** Rollback contract is "UI looks byte-equivalent to v1.0 when flag is on" — skeleton must match too.

### Q6: Should ?narrative=off persist across the session?

| Option | Description | Selected |
|--------|-------------|----------|
| Query param only — no persistence | URL is only source of truth. Refreshing without flag turns narrative back on. | ✓ |
| Query param sets sessionStorage | Persists until tab close. | |
| Query param sets localStorage | Persists across reloads. | |

**User's choice:** Query param only — no persistence
**Notes:** Minimal freeze surface (no extra storage keys), auditable contract.

---

## Version indicator (UI-07)

### Q7: Where on the UI should the v2.0 · <sha> indicator render?

| Option | Description | Selected |
|--------|-------------|----------|
| Bottom-right fixed corner | position:fixed bottom-right, muted, always visible. | ✓ |
| Top-right fixed corner | Same but top-right — collision risk with DevTools docked right. | |
| Footer inside main column | Scrolls with content; below the fold at paint. | |

**User's choice:** Bottom-right fixed corner
**Notes:** Bottom-right avoids DevTools collision at 1280px; live in-browser operator diagnostic.

### Q8: How should the git SHA be injected into the bundle?

| Option | Description | Selected |
|--------|-------------|----------|
| Vite define at build time from git rev-parse | vite.config.ts calls execSync inside try/catch, injects __GIT_SHA__ define. | ✓ |
| import.meta.env with VITE_GIT_SHA env var | Set env var as part of npm run build script. | |
| Baked into a generated TS file via prebuild script | scripts/inject-sha.js writes src/build-info.ts. | |

**User's choice:** Vite define at build time from git rev-parse
**Notes:** Deterministic per build, zero runtime cost, shared automatically between `build` and `build:mock` via vite.config.ts.

### Q9: What exact format should the indicator show?

| Option | Description | Selected |
|--------|-------------|----------|
| v2.0 · 7-char SHA | Matches ROADMAP.md Success Criterion 4 verbatim; middle-dot from Phase 4 convention. | ✓ |
| v2.0 · 7-char SHA · build time | Adds timestamp; overkill for single-shot demo. | |
| 2.0.0+sha (semver-prerelease style) | Machine-parseable but reads poorly at a glance. | |

**User's choice:** v2.0 · 7-char SHA
**Notes:** Verbatim match with ROADMAP success criterion. U+00B7 middle dot.

### Q10: Should the indicator always be visible, or only on hover/click?

| Option | Description | Selected |
|--------|-------------|----------|
| Always visible, muted | Low-opacity muted-foreground text, always in corner. | ✓ |
| Visible on hover over a small dot | Small 8px dot expands to full string on hover. | |
| Visible only when ?debug=1 query flag is set | Hidden by default. | |

**User's choice:** Always visible, muted
**Notes:** Core purpose is "defend against stale bundle" — a hidden indicator defeats the framing.

---

## Types + mock fixture + test posture

### Q11: How should TrackInfo TypeScript type be extended?

| Option | Description | Selected |
|--------|-------------|----------|
| Required fields (matches backend contract) | `usage_narrative: string; call_script: string;` both required. | ✓ |
| Optional fields (?) for defensive mock compat | Both optional for backward-compatible mock. | |
| Required on response type, Zod/runtime validation at hook | Required in TS plus runtime Zod validation. | |

**User's choice:** Required fields (matches backend contract)
**Notes:** Phase 6 fallback guarantees non-empty; optional would mask bugs. Phase 6 Pydantic is sole content guarantor — no second client-side validator.

### Q12: What content goes into the mock fixture for the new narrative fields?

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse Phase 6 committed fallback strings verbatim | Copy the 6 canonical fallback strings from agent/narrative/fallbacks.py. | ✓ |
| Hand-author fresh mock-specific strings | Write 6 new strings for the mock fixture. | |
| Copy Phase 6 fallbacks at build time via a script | sync-mock-narratives.js regenerates TS fixture. | |

**User's choice:** Reuse Phase 6 committed fallback strings verbatim
**Notes:** Build:mock dist indistinguishable from live for seeded personas. In-file comment documents the sync rule (same discipline as $30/$55 numbers).

### Q13: What level of test coverage should Phase 8 commit?

| Option | Description | Selected |
|--------|-------------|----------|
| Component + hook tests (vitest) | RecommendationCard renders both rows, flag hides both, skeleton shape, mock fixture type-checks. | ✓ |
| Component tests + UI-08 layout shift assertion | Plus getBoundingClientRect check — jsdom layout is synthetic. | |
| Component tests + Playwright visual regression | Plus Playwright snapshot — adds new dep and freeze surface. | |

**User's choice:** Component + hook tests (vitest)
**Notes:** Layout validation stays a human UAT step at closeout. No new test dependencies.

### Q14: Should the mock fixture validate the same content rules as Phase 6's validator?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — vitest asserts mock strings pass the same rules | Vitest scans MOCK_RECOMMENDATIONS for digit/$/£/€/% and word-count caps. | ✓ |
| No — mock is authored once and reviewed in PR | Treat as a reviewed artefact; PR review catches typos. | |

**User's choice:** Yes — vitest asserts mock strings pass the same rules
**Notes:** Mirrors Phase 6 `test_fallbacks_pass_validator`. Catches mock authoring drift at the UI layer. No new deps.

---

## Claude's Discretion

Planner / executor discretion on:

- Exact vertical spacing between narrative, methodology, and call_script rows (default to existing `space-y-4` pattern, tighten during human UAT if needed).
- Whether to introduce a `TrackAccentBorder` utility or inline `border-l-4 border-l-emerald-600` / `border-l-blue-600` (recommend inline to match TRACK_CONFIG pattern).
- `__GIT_SHA__` TypeScript declaration location (recommend `ui/src/vite-env.d.ts`).
- Call_script quote marks: inline text (U+275D / U+275E) vs CSS pseudo-elements vs lucide Quote icon (recommend inline text).
- Whether `flags.ts` re-exports `__GIT_SHA__` (recommend no — narrowly scoped module).
- Opacity of the version indicator (starting at `opacity-60`; tighten if too prominent).

## Deferred Ideas

Captured in CONTEXT.md `<deferred>` section:

- Presenter tooltip (alt-click raw LLM + verdict) — requires `_narrative_source` to survive API Lambda (contradicts Phase 7 D-06).
- Playwright visual regression — adds freeze surface for single-shot demo.
- `getBoundingClientRect` layout-shift assertion — jsdom layout is synthetic.
- Streaming narrative, regenerate button — locked OUT OF SCOPE at requirements stage.
- Cache narrative per persona for deterministic rehearsal output — variance currently tolerated.
- Second URL flag to hide version indicator — indicator is a permanent build marker by design.
- localStorage / sessionStorage for narrative flag — URL-only is simpler.
- Zod runtime response validation — Phase 6 Pydantic is sole content guarantor.
- Extracting `NarrativeSkeleton` into its own component — inline keeps contract auditable.
- Build-time `fallbacks.py` → TS mock sync script — 6 strings, manual discipline sufficient.
- Build timestamp in indicator — SHA alone fully identifies the build.
- CloudWatch alarm on client-side narrative render failure — v3.0 production hardening.
- Separate /debug route — not needed; corner marker + DevTools suffice.
