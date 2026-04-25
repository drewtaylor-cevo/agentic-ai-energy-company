# Phase 4: Agent-Assist UI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-24
**Phase:** 04-agent-assist-ui
**Areas discussed:** API wiring, Deploy target, Demo ergonomics, Testing depth

---

## API wiring

### Q1. Fetching approach

| Option | Description | Selected |
|--------|-------------|----------|
| Native fetch + custom hook | Tiny bespoke useRecommendations hook built on fetch + AbortController. ~40 LOC. Zero deps added. | ✓ |
| TanStack Query | Full-fat cache + retry + dedup library. Adds ~13 KB gzip and a QueryClient wrapper at root. | |
| SWR | Lighter than TanStack (~4 KB). Handy stale-while-revalidate behavior, but UI-SPEC clears previous results on a new query. | |

**User's choice:** Native fetch + custom hook
**Notes:** One endpoint, one screen, no cross-query cache needed — a library is weight without benefit.

### Q2. Base URL configuration

| Option | Description | Selected |
|--------|-------------|----------|
| VITE_API_URL build-time env | Standard Vite pattern: .env.development / .env.production. Rebuild to switch. | ✓ |
| Vite dev proxy + relative URL | Dev proxies /api/* to deployed API; prod uses same-origin relative path. | |
| Runtime config.json fetched at load | UI fetches /config.json on startup. Lets you rebrand envs without rebuilding. | |

**User's choice:** VITE_API_URL build-time env
**Notes:** Works for dev-server-only demo AND any future static-deploy target without refactor.

### Q3. Fallback when API unset or unreachable

| Option | Description | Selected |
|--------|-------------|----------|
| Local mock server mode | If VITE_API_URL is unset, useRecommendations returns data from a local JSON fixture keyed by customer_id. | ✓ |
| Hard fail | VITE_API_URL required; build or runtime error if missing. | |
| Error alert only | Every lookup returns the 'Something went wrong' alert when URL is unset. | |

**User's choice:** Local mock server mode
**Notes:** Lets Phase 4 progress while Phase 3 deploy is deferred. Also demo safety net if API is flaky on the day.

### Q4. Retry policy

| Option | Description | Selected |
|--------|-------------|----------|
| No retry — operator re-submits | Silent retry is worse on a live call; error alert + operator re-click matches UI-SPEC. | ✓ |
| Auto-retry once on 5xx | Hides flaky cold starts but doubles worst-case latency against <3s. | |

**User's choice:** No retry — operator re-submits
**Notes:** Matches UI-SPEC's "Alert in place of result cards" contract verbatim.

---

## Deploy target

### Q1. Run target

| Option | Description | Selected |
|--------|-------------|----------|
| Local 'vite preview' of static build | Phase 4 produces ui/dist/; demo runs 'vite preview' on presenter laptop. | ✓ |
| Vite dev server (npm run dev) | HMR overlays and source-map failures risk surfacing red squares mid-demo. | |
| S3 + CloudFront static hosting | Professional URL, but adds CDK stack work and depends on Phase 3 deploy. | |
| Local 'vite preview' now, S3+CloudFront in Phase 5 | Same as option 1 but names the cloud deploy as a Phase 5 item. | |

**User's choice:** Local 'vite preview' of static build
**Notes:** No cloud moving parts, fastest cold start, works offline with mock mode, zero dev↔demo drift.

### Q2. CDK scope

| Option | Description | Selected |
|--------|-------------|----------|
| No CDK work in Phase 4 | Phase 4 is frontend-only. Any UI deploy infrastructure is explicit Phase 5 scope. | ✓ |
| Add UiHostingStack in Phase 4 | New CDK stack: S3 + CloudFront + deploy script. | |

**User's choice:** No CDK work in Phase 4
**Notes:** Keeps Phase 4 decoupled from Phase 3 live-deploy (itself deferred to Phase 5).

### Q3. Build verification

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — 'npm run build' + 'vite preview' smoke check | Build once, preview, verify all 3 personas at 1280px above the fold. | ✓ |
| No — dev-server verification only | Build verification deferred to Phase 5. | |

**User's choice:** Yes — 'npm run build' + 'vite preview' smoke check
**Notes:** Catches dev-only code that breaks in the prod build before Phase 5 depends on it.

---

## Demo ergonomics

### Q1. Persona quick-pick chips

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — visible persona chips | Three chips below the input; one-click populate of CUST-001/002/003. Presenter-safety. | ✓ |
| Yes, but hidden behind Alt+D | Keeps UI screenshot-clean; requires presenter handshake mid-call. | |
| No quick-pick — type the ID every time | Matches UI-SPEC as written. Risk: typo during hero moment. | |

**User's choice:** Yes — visible persona chips
**Notes:** Additive, doesn't affect UI-SPEC card contract, zero-typo path for live demo.

### Q2. Input normalization

| Option | Description | Selected |
|--------|-------------|----------|
| Fix placeholder + accept both, auto-normalize | Update UI-SPEC to 'e.g. CUST-001234'; auto-insert dash and uppercase on submit. | ✓ |
| Fix placeholder only — strict input | Drop the dash → 400 alert. Punishes a common typing pattern. | |
| Accept both without touching UI-SPEC | Leaves documented spec drift. | |

**User's choice:** Fix placeholder + accept both, auto-normalize
**Notes:** UI-SPEC amendment at line 109 from 'e.g. CUST001234' to 'e.g. CUST-001234'. Tracked as a planner task.

### Q3. Persona data source

| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded in personas.ts constant | Small {id, label} constant mirroring the 3 Phase 1 dummy personas. | ✓ |
| Fetched from a new /personas endpoint | Requires new backend endpoint — scope creep. | |
| Read from same JSON fixture as mock fallback | Cleaner single-source, but couples personas to fixture layout. | |

**User's choice:** Hardcoded in personas.ts constant
**Notes:** Zero coupling to API. Visible in source. Single import surface for chips.

### Q4. Enter key behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Both submit — Enter in input OR click CTA | Standard <form onSubmit>, CTA is type='submit'. | ✓ |
| Button-only | Less surprising but unusual and slower on a live call. | |

**User's choice:** Both submit
**Notes:** No cognitive load on the operator mid-call.

---

## Testing depth

### Q1. Testing bar

| Option | Description | Selected |
|--------|-------------|----------|
| Vitest + RTL for logic, manual smoke for UI | Unit-test the fetch hook + normalization. Skip component-render tests. | ✓ |
| Vitest + RTL for logic AND component render | Adds RTL tests for card copy, error alert replacement, skeleton display. | |
| Vitest + RTL + Playwright end-to-end | Adds browser-driver infrastructure for 3 screens of flow. | |
| Manual only — no automated UI tests | Rely on Phase 5 persona rehearsal. Risk of silent logic regressions. | |

**User's choice:** Vitest + RTL for logic, manual smoke for UI
**Notes:** UI-SPEC locks all strings, so component-render tests would just duplicate the spec. Phase 5 covers end-to-end rehearsal.

### Q2. Test runner

| Option | Description | Selected |
|--------|-------------|----------|
| Vitest + @testing-library/react + jsdom | Vite-era stack. Reuses Vite config. Minimal dev-dep additions. | ✓ |
| Jest + @testing-library/react | Parallel config + transform pipeline for no benefit. | |

**User's choice:** Vitest + @testing-library/react + jsdom
**Notes:** Matches the Vite 8 / React 19 generation in package.json.

---

## Claude's Discretion

- File structure under `ui/src/` — exact folder layout (components, hooks, lib, flat, or feature-sliced)
- Mock fixture location and format
- Error-status detection strategy inside the hook (switch vs mapping table)
- Loading skeleton specifics (dimensions, row count, animation timing) within the "no layout shift" guarantee
- Cold-start reassurance copy (optional "Still looking…" hint after ~3s)
- TypeScript strictness flags in tsconfig.app.json
- Shadcn init execution order (one-time script vs README setup block)
- Favicon and `<title>` tag
- Client-side observability (console.error acceptable; no Sentry expected)

## Deferred Ideas

- S3 + CloudFront UI hosting → Phase 5 if narrative requires shareable URL
- UI-03 call-script snippet card → v2
- UI-04 usage narrative card → v2
- Playwright end-to-end smoke → considered and rejected; Phase 5 persona rehearsal covers it
- Component-level RTL tests for card rendering → considered and rejected; duplicates UI-SPEC
- Sentry / LogRocket → not needed for dummy-data demo
- Cold-start pre-warm (DEMO-03) → v2, already deferred in PROJECT.md
- Alt+D hidden-chip affordance → considered and rejected; visible chips clearer
- /personas backend endpoint → considered and rejected; scope creep
- Custom domain / branded URL → Phase 5 if needed
- Mobile / responsive layout beyond UI-SPEC <768px stack → Out of Scope in REQUIREMENTS
