---
phase: 04-agent-assist-ui
plan: 01
subsystem: ui
tags: [shadcn, tailwindcss, vite, vitest, react, typescript, lucide, inter-font]

requires:
  - phase: 03-backend-api
    provides: "GET /recommendations/{customer_id} contract consumed by UI (TrackInfo/RecommendationResponse schema, ^CUST-\\d{3,6}$ regex, error taxonomy)"
provides:
  - "Buildable ui/ package: npm run build exits 0 with dist/ output"
  - "shadcn/ui components.json pinned to style=new-york, baseColor=slate, cssVariables=true (UI-SPEC contract)"
  - "All 7 shadcn primitives pulled and importable from @/components/ui: button, input, card, label, skeleton, alert, badge"
  - "Tailwind CSS v4 wired via @tailwindcss/vite plugin, slate palette CSS variables in src/index.css"
  - "Vitest 4 configured with jsdom + @testing-library/react + @testing-library/jest-dom setup; npx vitest run --passWithNoTests exits 0"
  - "@ path alias resolves in both tsc and Vite (tsconfig.app.json + vite.config.ts)"
  - "Inter font (400/600) preconnected and linked in index.html; page title 'Tariff Recommendations'"
  - ".env.development and .env.production both committed with empty VITE_API_URL (D-02/D-03 mock-fallback default)"
  - "Vite starter scaffold fully removed per D-15 (App.css, hero.png, react.svg, vite.svg)"
  - "UI-SPEC amended per D-11: Form placeholder is 'e.g. CUST-001234' (dashed, canonical)"
affects:
  - 04-02-api-client-and-hook
  - 04-03-presentation-components
  - 04-04-layout-composition
  - 04-05-build-verify-and-smoke
  - Phase 5 presenter rehearsal (build output + preview command are load-bearing)

tech-stack:
  added:
    - "tailwindcss 4.2 + @tailwindcss/vite 4.2 (Tailwind v4 runtime + Vite plugin)"
    - "class-variance-authority 0.7 + clsx 2.1 + tailwind-merge 3.5 (shadcn's cn() helper stack)"
    - "tw-animate-css 1.4 (shadcn-recommended animation layer)"
    - "lucide-react 1.9 (icon library, UI-SPEC §Design System)"
    - "radix-ui 1.4 (pulled as dep by shadcn button + label + badge)"
    - "vitest 4.1 + @testing-library/react 16 + @testing-library/jest-dom 6 + jsdom 29"
  patterns:
    - "shadcn CLI v4 add pattern: `npx shadcn@latest add …` writes into `@/components/ui/`, then manually moved to src/components/ui (CLI v4 quirk; alias `@` not auto-resolved to src when the target directory is new)"
    - "Tailwind v4 CSS-first theme via @theme inline + @import 'tailwindcss' + CSS custom properties (no tailwind.config.js needed, per Tailwind v4 contract)"
    - "Vitest 4 config lives inline in vite.config.ts under `test:` with /// <reference types=\"vitest/config\" />"
    - "shadcn components.json is hand-authored (not CLI-generated) to honour UI-SPEC's locked new-york/slate preset — CLI v4 deprecated the matching flags"

key-files:
  created:
    - "ui/components.json — shadcn config, new-york/slate preset"
    - "ui/src/lib/utils.ts — cn() helper via clsx + tailwind-merge"
    - "ui/src/test-setup.ts — @testing-library/jest-dom/vitest matchers"
    - "ui/src/components/ui/button.tsx, input.tsx, card.tsx, label.tsx, skeleton.tsx, alert.tsx, badge.tsx — 7 shadcn primitives"
    - "ui/.env.development — VITE_API_URL= (empty, mock fallback)"
    - "ui/.env.production — VITE_API_URL= (empty, mock fallback)"
  modified:
    - "ui/package.json — added Tailwind v4, shadcn runtime stack, Vitest 4 test stack, lucide-react, tw-animate-css, radix-ui; added test + test:watch scripts"
    - "ui/vite.config.ts — added @tailwindcss/vite plugin, @ path alias, Vitest config block (jsdom, globals, setupFiles)"
    - "ui/tsconfig.app.json — added paths alias for @/* → ./src/*"
    - "ui/src/index.css — replaced Vite starter theme with Tailwind v4 @theme + shadcn slate CSS variables, Inter font-family body rule"
    - "ui/src/App.tsx — minimal placeholder with bg-background/text-foreground/text-muted-foreground to prove theme wires"
    - "ui/index.html — title 'Tariff Recommendations', Inter font preconnect + Google Fonts link"
    - ".planning/phases/04-agent-assist-ui/04-UI-SPEC.md — D-11 amendment, placeholder now 'e.g. CUST-001234'"
  deleted:
    - "ui/src/App.css — Vite starter CSS (D-15)"
    - "ui/src/assets/react.svg, vite.svg, hero.png — Vite starter assets (D-15)"

key-decisions:
  - "Honour UI-SPEC preset by hand-authoring components.json (new-york/slate) rather than invoking the deprecated `npx shadcn init --style new-york --base-color slate` flags — modern shadcn CLI v4 only exposes presets (Nova/Vega/Maia/...) and would otherwise select radix-nova + neutral"
  - "Use Tailwind v4 (not v3) because it is now the shadcn default and requires zero tailwind.config.js — theme lives in src/index.css via @theme inline"
  - "Drop deprecated `baseUrl` from tsconfig.app.json — TS 7 removes it; TS 6 infers it from the tsconfig location when `paths` is present"
  - "Use `/// <reference types=\"vitest/config\" />` (plural package) so Vite's `UserConfig` merges Vitest's `test` property at typecheck time"

patterns-established:
  - "shadcn components pulled into `src/components/ui/**` and imported via `@/components/ui/<name>` — the canonical alias path future plans will use"
  - "Mock-mode default via empty VITE_API_URL — production build also defaults to mock for demo safety (D-03), live API only when the env var is set and the app is rebuilt"
  - "Tailwind/shadcn theme classes validate via `bg-background`, `text-foreground`, `text-muted-foreground` — if a future plan breaks the theme variables, these class renders will surface it"

requirements-completed:
  - UI-01
  - UI-02

duration: 8min
completed: 2026-04-24
---

# Phase 4 Plan 01: UI Scaffold & Toolchain Summary

**shadcn/ui (new-york/slate) + Tailwind v4 + Vitest 4 scaffold with all 7 primitives, Inter font, mock-mode env, and Vite starter purged — `npm run build` green.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-24T10:31:30Z
- **Completed:** 2026-04-24T10:39:37Z
- **Tasks:** 2 / 2
- **Files changed:** 17 modified/deleted + 11 created = 28 (counting package-lock)

## Accomplishments

- Entire UI toolchain stood up from a bare Vite scaffold: Tailwind v4, shadcn/ui components.json, Vitest 4 + jsdom + @testing-library/react.
- All 7 shadcn primitives (button, input, card, label, skeleton, alert, badge) pulled, moved to `src/components/ui/`, and compiling cleanly against the Tailwind v4 + slate theme.
- Vite starter content (counter App, hero image, React/Vite logos, starter CSS) removed in full per D-15; replacement `App.tsx` exercises `bg-background` / `text-foreground` / `text-muted-foreground` so theme wiring is provable.
- Inter font preconnected and applied on `body`; page title set to `Tariff Recommendations`.
- `.env.development` + `.env.production` committed with empty `VITE_API_URL` so the default demo build is mock-mode (D-03 safety net).
- UI-SPEC §Copywriting placeholder amended per D-11 (`CUST001234` → `CUST-001234`) so the spec matches the API's canonical `^CUST-\d{3,6}$` regex.
- `npm run build` ships `dist/index.html` (0.72 kB), CSS bundle (24.68 kB), JS bundle (190.72 kB). `npx vitest run --passWithNoTests` exits 0.

## Task Commits

Each task was committed atomically:

1. **Task 1: Initialize shadcn/ui, install dependencies, configure Vitest** — `7bd5eda` (feat)
2. **Task 2: Pull shadcn components, remove starter scaffold, amend UI-SPEC D-11** — `dbeda48` (feat)

_(The final docs commit for this SUMMARY + STATE will be recorded by the orchestrator once the wave completes.)_

## Files Created / Modified / Deleted

**Created:**
- `ui/components.json` — shadcn preset pinned to new-york / slate / cssVariables
- `ui/src/lib/utils.ts` — `cn()` via clsx + tailwind-merge
- `ui/src/test-setup.ts` — jest-dom matcher registration
- `ui/src/components/ui/{button,input,card,label,skeleton,alert,badge}.tsx` — 7 shadcn primitives
- `ui/.env.development`, `ui/.env.production` — empty `VITE_API_URL` for mock-mode default

**Modified:**
- `ui/package.json`, `ui/package-lock.json` — Tailwind v4 + shadcn runtime + Vitest stack + scripts
- `ui/vite.config.ts` — Tailwind plugin, `@` alias, Vitest `test` block
- `ui/tsconfig.app.json` — `@/*` paths alias
- `ui/src/index.css` — Tailwind v4 + shadcn slate CSS variables, Inter body font
- `ui/src/App.tsx` — minimal placeholder exercising theme classes
- `ui/index.html` — title + Inter font link
- `.planning/phases/04-agent-assist-ui/04-UI-SPEC.md` — D-11 placeholder amendment

**Deleted (D-15, intentional):**
- `ui/src/App.css`, `ui/src/assets/hero.png`, `ui/src/assets/react.svg`, `ui/src/assets/vite.svg`

## Decisions Made

- Hand-authored `components.json` to preserve UI-SPEC's locked `new-york` / `slate` preset because shadcn CLI v4 no longer exposes those flags (the modern CLI is preset-driven with Nova/Vega/… and defaults to `radix-nova` / `neutral`). Writing the file manually keeps the UI-SPEC contract intact without coupling the project to a preset we did not select.
- Adopted Tailwind v4 + `@tailwindcss/vite` (not v3 + `tailwind.config.js`) because Tailwind v4 is the current shadcn default and removes the config-file step; theming lives in `src/index.css` via `@theme inline`.
- Dropped `baseUrl` from `tsconfig.app.json` after TypeScript 6 reported `TS5101` (deprecated, removed in TS 7). Modern TS resolves `paths` against the tsconfig's directory when `baseUrl` is absent, so the `@/*` alias still works.
- Added `/// <reference types="vitest/config" />` to `vite.config.ts` (instead of the plan's `vitest`) so Vite's `UserConfig` type merges Vitest 4's `test` property and `npm run build` typechecks.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 – Blocking] shadcn CLI v4 removed `--style new-york --base-color slate --css-variables` flags**
- **Found during:** Task 1 (Initialize shadcn/ui)
- **Issue:** The plan's exact invocation `npx shadcn@latest init --style new-york --base-color slate --css-variables` is no longer valid in shadcn CLI v4 (2026-03 release). The CLI errors with `unknown option '--base-color'`, scaffolds a fresh project under a new directory, and requires a preset (Nova/Vega/…) whose style is `radix-nova` and default base is `neutral`. Running the modern init over the existing `ui/` fails with "No Tailwind CSS configuration found", meaning it expects Tailwind to already be present.
- **Fix:** Installed Tailwind v4 + required shadcn deps (`@tailwindcss/vite`, `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `tw-animate-css`) directly via `npm install`; hand-authored `components.json` with the UI-SPEC-mandated `"style": "new-york"` + `"baseColor": "slate"` + `"cssVariables": true`; wrote `src/index.css` with Tailwind v4 `@theme inline` + shadcn's canonical slate HSL CSS variables; added the `@` path alias to both `tsconfig.app.json` and `vite.config.ts`; added the Vitest config block to `vite.config.ts`. Effect is identical to what the legacy `shadcn init` flags produced — same `components.json` contents, same theme variables, same alias.
- **Files modified:** `ui/package.json`, `ui/components.json` (new), `ui/src/index.css`, `ui/tsconfig.app.json`, `ui/vite.config.ts`, `ui/src/lib/utils.ts` (new), `ui/src/test-setup.ts` (new)
- **Verification:** `grep '"style": "new-york"' ui/components.json` + `grep '"baseColor": "slate"' ui/components.json` both match; `npm run build` exits 0; `npx vitest run --passWithNoTests` exits 0; `ui/dist/` renders the placeholder.
- **Committed in:** `7bd5eda` (Task 1 commit)

**2. [Rule 3 – Blocking] shadcn CLI v4 wrote components to a literal `@/components/ui/` directory instead of resolving the alias**
- **Found during:** Task 2 (Pull shadcn components)
- **Issue:** `npx shadcn@latest add button input card label skeleton alert badge -y` printed "Created 7 files: @/components/ui/button.tsx …" but wrote them to `./@/components/ui/*.tsx` in the project root — the `@` alias from `components.json` was not resolved to `src/` by the CLI. This is a known quirk of shadcn CLI v4 when adding to a pre-existing project not bootstrapped by `init -t vite`.
- **Fix:** Created the correct target directory and moved the files: `mkdir -p src/components/ui && mv "@/components/ui/"*.tsx src/components/ui/ && rm -rf "@"`. All 7 component files now live under `src/components/ui/` and import `@/lib/utils` (which resolves correctly via the configured alias).
- **Files modified:** Moved `button.tsx, input.tsx, card.tsx, label.tsx, skeleton.tsx, alert.tsx, badge.tsx` into `ui/src/components/ui/`; deleted the stray top-level `@` directory.
- **Verification:** `ls src/components/ui/` lists all 7; `head -5 button.tsx` confirms `import { cn } from "@/lib/utils"`; `npm run build` succeeds.
- **Committed in:** `dbeda48` (Task 2 commit)

**3. [Rule 1 – Bug] `tsconfig.app.json` used deprecated `baseUrl`**
- **Found during:** Task 2 build verification
- **Issue:** The Task 1 tsconfig edit added `"baseUrl": "."` alongside `"paths"`. TypeScript 6.0 reports `TS5101: Option 'baseUrl' is deprecated and will stop functioning in TypeScript 7.0`, which breaks `tsc -b` (and therefore `npm run build`).
- **Fix:** Removed `baseUrl` and kept `paths: { "@/*": ["./src/*"] }`. Modern TypeScript resolves `paths` relative to the tsconfig file location when `baseUrl` is absent, so the `@/*` alias still works identically.
- **Files modified:** `ui/tsconfig.app.json`
- **Verification:** `npm run build` exits 0; imports of `@/lib/utils` resolve in all 7 shadcn components.
- **Committed in:** `dbeda48` (Task 2 commit)

**4. [Rule 1 – Bug] `vite.config.ts` `test` property did not typecheck against Vite 8's `UserConfigExport`**
- **Found during:** Task 2 build verification
- **Issue:** The Task 1 triple-slash directive `/// <reference types="vitest" />` (singular) does not expose Vitest 4's `UserConfig` augmentation, so `tsc -b` reported `TS2769 … 'test' does not exist in type 'UserConfigExport'`. Per Vitest 4 docs, the correct directive is `/// <reference types="vitest/config" />` (subpath).
- **Fix:** Changed `/// <reference types="vitest" />` → `/// <reference types="vitest/config" />`. The `test` block now typechecks and Vitest picks up `environment`, `globals`, `setupFiles`.
- **Files modified:** `ui/vite.config.ts`
- **Verification:** `npm run build` exits 0; `npx vitest run --passWithNoTests` exits 0 and honours the jsdom + setup files.
- **Committed in:** `dbeda48` (Task 2 commit)

**5. [Rule 2 – Missing Critical] Removed all three Vite starter assets, not only `react.svg`**
- **Found during:** Task 2 (Remove starter scaffold)
- **Issue:** The plan's Task 2 step 2 names only `App.css` + `assets/react.svg` for deletion, but D-15 says the starter scaffold is "replaced, not extended … removed in full" and the new `App.tsx` does not import any of the three starter images. Leaving `vite.svg` and `hero.png` behind would contradict D-15 and would hand-wave a concrete decision in the design record.
- **Fix:** Also deleted `ui/src/assets/vite.svg` and `ui/src/assets/hero.png`. The `ui/src/assets/` directory is left in place (empty) so future plans can drop fresh assets per D-15.
- **Files modified:** Deleted `ui/src/assets/vite.svg`, `ui/src/assets/hero.png`.
- **Verification:** `ls src/assets` returns empty; `npm run build` succeeds (no broken imports); no code references any starter asset (`grep -r "react.svg\|vite.svg\|hero.png" ui/src` returns empty).
- **Committed in:** `dbeda48` (Task 2 commit)

---

**Total deviations:** 5 auto-fixed (3 blocking Rule 3 equivalents — all stemming from the shadcn CLI v4 redesign that post-dates the plan — plus 1 genuine bug in the tsconfig edit, 1 type-reference bug in the Vitest directive, and 1 Rule 2 enforcement of D-15's "removed in full" intent).
**Impact on plan:** All deviations preserved the plan's intent. The delivered artifacts (components.json preset, alias paths, Vitest jsdom config, 7 components, removed starter, amended UI-SPEC) match the must_haves table exactly. No scope creep; no architectural changes.

## Issues Encountered

- `npx shadcn@latest init` on the existing `ui/` directory refused to run ("No Tailwind CSS configuration found") because CLI v4 expects a fresh project scaffold. Resolved by pre-installing Tailwind + shadcn deps, then running `shadcn add` for the 7 components.
- A standalone `@/components/ui/` directory was written at the project root by `shadcn add` (alias not auto-resolved to `src/`). Resolved by moving the files and removing the stray top-level `@` directory before commit.

## Next Plan Readiness

- **Ready for Plan 04-02 (Wave 2: API client + `useRecommendations` hook):** `@/lib/utils` exists, `@/components/ui/*` all importable, Vitest 4 + jsdom + testing-library installed, `VITE_API_URL` env-var wiring prepared by empty dev/prod env files, and the project builds.
- **Ready for Plan 04-03 (Wave 2: Presentation components):** shadcn `Button`, `Input`, `Card` + subcomponents, `Label`, `Skeleton`, `Alert`, `Badge` are all present with the canonical `@/components/ui` import surface; Inter font is applied globally; slate CSS variables (`bg-background`, `text-foreground`, `text-muted-foreground`, `border`) resolve at build time.
- **Ready for Plan 04-04 (Wave 3: Composition):** `src/App.tsx` is a trivial placeholder that Plan 04-04 will overwrite; no accidental coupling to the scaffold.
- **Ready for Plan 04-05 (Wave 4: Build + smoke):** `npm run build` is already green; the final smoke plan only needs to assert the composed app renders the two cards above the fold at 1280×800.

## Self-Check: PASSED

- Created files exist:
  - `ui/components.json` — FOUND
  - `ui/src/lib/utils.ts` — FOUND
  - `ui/src/test-setup.ts` — FOUND
  - `ui/src/components/ui/button.tsx` — FOUND
  - `ui/src/components/ui/input.tsx` — FOUND
  - `ui/src/components/ui/card.tsx` — FOUND
  - `ui/src/components/ui/label.tsx` — FOUND
  - `ui/src/components/ui/skeleton.tsx` — FOUND
  - `ui/src/components/ui/alert.tsx` — FOUND
  - `ui/src/components/ui/badge.tsx` — FOUND
  - `ui/.env.development` — FOUND
  - `ui/.env.production` — FOUND
- Task commits exist in git:
  - `7bd5eda` (Task 1) — FOUND
  - `dbeda48` (Task 2) — FOUND
- Key success criteria verified:
  - `grep '"style": "new-york"' ui/components.json` — MATCH
  - `grep '"baseColor": "slate"' ui/components.json` — MATCH
  - `grep 'Tariff Recommendations' ui/index.html` — MATCH
  - `grep 'CUST-001234' .planning/phases/04-agent-assist-ui/04-UI-SPEC.md` — MATCH
  - `npm run build` — exit 0
  - `npx vitest run --passWithNoTests` — exit 0

---
*Phase: 04-agent-assist-ui*
*Completed: 2026-04-24*
