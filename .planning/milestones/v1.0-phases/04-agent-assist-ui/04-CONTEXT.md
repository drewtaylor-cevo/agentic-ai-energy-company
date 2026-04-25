# Phase 4: Agent-Assist UI - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the React + Vite single-page agent-assist panel that consumes the Phase 3 `GET /recommendations/{customer_id}` endpoint and renders two equal-weight recommendation cards (Green + Cheapest) above the fold on a 1280px desktop in under 3 seconds. The deliverable is a buildable `ui/` package (`npm run build` → `ui/dist/`) that runs via `vite preview` on the presenter's laptop and exercises the full demo flow for all 3 personas.

**All visual, copy, color, typography, spacing, layout, and error-UX decisions are locked by `04-UI-SPEC.md`.** This context only covers HOW the UI is wired to the API, where it runs, how it handles demo ergonomics, and how it is tested — the implementation-level decisions UI-SPEC does not cover.

New capabilities (S3+CloudFront hosting, live CRM integration, /personas endpoint, LLM-generated call scripts UI-03, usage narratives UI-04, mobile responsive layout beyond UI-SPEC's stacked <768px fallback) belong in Phase 5 or remain v2-deferred.

</domain>

<decisions>
## Implementation Decisions

### API Wiring
- **D-01:** **Native `fetch` + custom `useRecommendations(customerId)` hook** — no data-fetching library. One endpoint, one screen, no cross-query cache needed (UI-SPEC mandates clearing previous results on re-query). ~40 LOC over AbortController. Adds zero deps. TanStack Query / SWR rejected as weight without benefit for a single-endpoint demo.
- **D-02:** **`VITE_API_URL` build-time env** — standard Vite pattern. `.env.development` for dev, `.env.production` for the static demo build. Rebuild to switch environments. Works uniformly for both the Phase 4 local `vite preview` path and any future static-deploy target without refactor. Runtime config.json rejected (overkill); Vite dev-proxy rejected (Phase 3 deploy deferred, no shared origin at demo time).
- **D-03:** **Mock-server fallback when `VITE_API_URL` is unset** — `useRecommendations` returns data from a local JSON fixture keyed by customer_id (the 3 personas baked into Phase 1 dummy data). Lets the UI be developed and demoed fully offline. Real API is used only when `VITE_API_URL` is set. Also serves as demo safety net if the API is flaky on the day. Fixture MUST be reconciled against `infrastructure/seed_data/` and the deterministic savings from Phase 1 (Green ≈ $30/mo, Cheapest ≈ $55/mo on the flagship persona per DEMO-02) so mock output matches live API output exactly.
- **D-04:** **No auto-retry on failure** — operator re-submits. A silent retry that takes another 3–5s is worse on a live call than surfacing the error immediately. Operator sees the UI-SPEC error alert (504/502/500 copy) and re-clicks "Look up customer." Matches UI-SPEC's "Alert in place of result cards" contract verbatim.

### Deployment Target
- **D-05:** **Local `vite preview` of the static build** is the Phase 4 run target. Phase 4 produces `ui/dist/` via `npm run build`; demo runs `vite preview` on the presenter's laptop. No cloud moving parts, fastest cold start, works offline with mock mode, zero dev↔demo drift. S3+CloudFront hosting deferred to Phase 5 (only if the demo narrative requires a shareable URL).
- **D-06:** **No CDK infrastructure changes in Phase 4.** Phase 4 is frontend-only. No new stacks; no amendments to `FoundationStack` / `AgentCoreStack` / `BackendApiStack`. This keeps Phase 4 decoupled from the Phase 3 live-deploy (which is itself deferred to Phase 5).
- **D-07:** **Production-build verification is a Phase 4 plan step** — `npm run build` must succeed and a manual `vite preview` smoke (all 3 personas render above the fold at 1280px, both cards equal-width, no layout shift during skeleton→cards) must pass before Phase 4 closes. Catches dev-only code that breaks in the prod build before Phase 5 rehearsal depends on it.

### Demo Ergonomics
- **D-08:** **Visible persona quick-pick chips below the input** — three chips labeled with the 3 personas (e.g. "CUST-001 · High usage", "CUST-002 · Mid usage", "CUST-003 · Low usage"). One click populates the input with the customer ID. Presenter-safety during a live call — zero-typo path. Additive to UI-SPEC's input + CTA; does not affect the locked card contract or the neutral-between-tracks invariant. Chips sit between the `Input` and the empty state / result cards, below the `md` form-to-results rhythm.
- **D-09:** **Persona IDs hardcoded in `ui/src/personas.ts`** — small constant of `{id, label}` objects mirroring the 3 Phase 1 dummy personas. No /personas API call (scope creep into backend), no coupling to the mock fixture. Single import surface that both the quick-pick chips and the mock fallback consume.
- **D-10:** **Auto-normalize input before submit** — trim whitespace, uppercase, and auto-insert the dash if the operator typed `CUST001234`. Final value must match `^CUST-\d{3,6}$` (the API regex) before the fetch fires; otherwise the 400 alert is shown from client-side. Forgiving of the common no-dash typing pattern without masking the canonical format in the URL.
- **D-11:** **UI-SPEC placeholder amendment** — change `Form placeholder` from `e.g. CUST001234` to `e.g. CUST-001234` to match the API canonical format (`^CUST-\d{3,6}$`, per api_lambda/handler.py:27 and lambda/handler.py regex). This is a small amendment to UI-SPEC.md, tracked as a planner task. Canonical format is dashed; the UI accepts both forms and normalizes.
- **D-12:** **Enter and CTA both submit** — input wrapped in `<form onSubmit>`, CTA is `type="submit"`. Standard form pattern, zero cognitive load during a live call. Operator can Tab-from-input to button, or press Enter, or click — all paths submit.

### Testing Depth
- **D-13:** **Vitest + `@testing-library/react` + `jsdom`** — Vite-era stack, reuses Vite's config, fast startup, minimal dev-dep additions aligned with Vite 8 / React 19. Jest rejected (parallel config + transform pipeline for zero benefit on a small codebase).
- **D-14:** **Logic-layer unit tests only; visual verification is manual.** Unit-test surface:
  - `useRecommendations` hook: success path, 400 / 404 / 504 / 502 / 500 status mapping, network failure, mock-fallback branch when `VITE_API_URL` unset.
  - Input normalization: dash insertion, uppercasing, trimming, pre-submit regex gate.
  - Persona constant shape (IDs satisfy the regex).
  
  No component-render tests (UI-SPEC locks all strings — drift risk is low and RTL tests for string equality would just duplicate the spec). No Playwright (browser-driver infrastructure is weight for 3 screens of flow; Phase 5 persona rehearsal provides real end-to-end verification).

### Scaffold Removal
- **D-15:** **`ui/src/App.tsx`, `App.css`, and the `assets/` starter images are replaced, not extended.** The current Vite starter content (hero image, counter, Vite/React link cards) is removed in full during Phase 4 setup. Any legitimate assets (e.g., a tariff/utility icon if added) belong under `ui/src/assets/` with new filenames.

### Claude's Discretion
- **File structure under `ui/src/`** — exact folder layout (`components/`, `hooks/`, `lib/`, flat, or feature-sliced). Planner picks based on scope (one screen, one hook, ~6 components).
- **Mock fixture location and format** — e.g., `ui/src/lib/mock/recommendations.json` vs inline TypeScript constants. Planner picks.
- **Error-status detection strategy inside the hook** — `response.status` switch vs a mapping table. Planner picks; must cover D-12 error codes from Phase 3 (400, 404, 500, 502, 504).
- **Loading skeleton specifics** — UI-SPEC mandates two equal-shape Skeleton placeholders during load. Exact dimensions, number of skeleton rows per card, animation timing are Claude's discretion within the spec's "no layout shift" guarantee.
- **Cold-start reassurance copy** — Phase 3 D-04 accepts cold-start latency; first invocation may be 5–10s. Planner may add an optional "Still looking…" secondary hint after ~3s of loading, or stay with the plain skeleton. Not a success criterion either way.
- **TypeScript strictness flags** — `tsconfig.app.json` tightening (strict null, exactOptionalPropertyTypes) at planner discretion.
- **Shadcn init execution order** — UI-SPEC line 28 mandates `npx shadcn@latest init` with preset `new-york` / `slate` / CSS vars as the first setup task; planner decides whether to run it via a one-time script or document it in a README setup block.
- **Favicon / page title** — UI-SPEC locks the page-body display text but not the `<title>` tag or favicon. Planner picks sensible defaults (`<title>Tariff Recommendations</title>` and a simple favicon consistent with the neutral-slate palette).
- **X-Ray / observability** — no client-side error reporting (Sentry, LogRocket) expected for a demo. Planner may add `console.error` at fetch failure points but no external service wiring.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Design Contract (load-bearing — do not re-derive)
- `.planning/phases/04-agent-assist-ui/04-UI-SPEC.md` — shadcn New York/Slate preset, Inter font, full spacing scale, typography roles, accent-only-differentiation color contract, full copywriting table (including all 5 error messages), components to pull (`button`, `input`, `card`, `label`, `skeleton`, `alert`, `badge`), interaction states (idle / loading / success / error / re-query), and the locked equal-cards contract. **If this spec conflicts with any other doc, this spec wins for everything visual, interactional, and textual.** Placeholder amendment per D-11 applies.

### Requirements
- `.planning/REQUIREMENTS.md` — Phase 4 maps to **UI-01** (both cards above the fold on 1280px desktop, no scroll during live call) and **UI-02** (customer ID to rendered cards in <3s; loading skeletons shown immediately). Mobile/responsive explicitly Out of Scope. OAuth/authentication Out of Scope.

### Project Context
- `.planning/PROJECT.md` — Core value, demo hook "customer lookup → instant personalised savings plan", call-centre-agent UX context (fast/scannable/actionable), constraint that recommendations are surfaced but never auto-applied. Desktop-first 1280px locked.

### Roadmap
- `.planning/ROADMAP.md` §Phase 4 — success criteria: both cards above the fold on 1280px, customer-ID-to-cards under 3s with skeleton-first rendering, each card shows plan name + monthly saving + annual equivalent + one-line methodology.

### Phase 3 API Contract (the entire interface Phase 4 consumes)
- `.planning/phases/03-backend-api/03-CONTEXT.md` — D-01 synchronous JSON response, D-02 pass-through shape `{"green": {plan_id, plan_name, saving_monthly, saving_annual}, "cheapest": {...}}`, D-10 `GET /recommendations/{customer_id}`, D-12 HTTP error taxonomy (400/404/500/502/504), D-09 CORS allow-all.
- `api_lambda/handler.py` — source of truth for request/response wire format and the canonical `^CUST-\d{3,6}$` regex (D-10, D-11). Error body shape `{"error": "<friendly message>"}`. Response body is whatever the agent emits for 200; `{"error": ...}` for non-200. UI parses status-code-first, then body.
- `agent/agent.py::RecommendationResponse` — authoritative per-track schema: `plan_id: str`, `plan_name: str`, `saving_monthly: float`, `saving_annual: float`. TypeScript types in the UI MUST mirror this exactly.

### Phase 1 Dummy Data (source of truth for mock fallback D-03 and persona constant D-09)
- `infrastructure/seed_data/` — the 3 persona billing profiles and expected Green/Cheapest savings. The UI's mock fixture and the `personas.ts` labels MUST be reconciled against this data so mock output matches live API output exactly (especially DEMO-02's $30 / $55 flagship targets).
- `lambda/handler.py::_validate_customer_id` — identical regex to D-10; defense-in-depth lives on the API side, UI normalization (D-10) happens before submit.

### Established Stack Patterns (from Phases 1–3)
- `pytest.ini`, `tests/conftest.py`, `tests/test_agent_smoke.py` — backend test shape. UI testing is Vitest (D-13) not pytest, so these are stylistic references only (e.g., consistent "offline unit + smoke" mental model).
- `app.py` — CDK stack registration; confirms no UI stack exists (aligns with D-06).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`ui/` Vite + React 19 + TypeScript scaffold is already in place** — `vite.config.ts`, `tsconfig.*`, `eslint.config.js`, `package.json` with React 19.2 / Vite 8 / TypeScript 6. No re-scaffold needed. Package name `ui`, module type `module`, standard Vite scripts (`dev`, `build`, `lint`, `preview`).
- **Phase 3 `api_lambda/handler.py`** — authoritative regex and error-status table. The UI's status-code mapping is a direct mirror.
- **Phase 2 `agent/agent.py::RecommendationResponse`** — authoritative per-track schema for TypeScript types.
- **Phase 1 `infrastructure/seed_data/`** — source data for the mock fallback fixture (D-03) and persona chip labels (D-09).

### Established Patterns
- **Stack-per-phase CDK** — Phase 4 explicitly does NOT continue this pattern (D-06); it is frontend-only.
- **Backend offline-unit + smoke-test split** — UI analog (D-14): Vitest unit tests for logic; manual smoke via the production build in `vite preview` (D-07) and Phase 5 persona rehearsal.
- **Shadcn not yet initialized** — `ui/package.json` has no Tailwind, no shadcn, no `components.json`. UI-SPEC explicitly calls this out (`shadcn_initialized: false`). First Phase 4 setup task is `npx shadcn@latest init` with the locked preset.
- **us-east-1 region** — hardcoded in `app.py`; irrelevant to Phase 4 (no CDK work), but `VITE_API_URL` at demo time will point at an AWS us-east-1 endpoint once Phase 5 deploys.

### Integration Points
- **Upstream:** UI calls `GET ${VITE_API_URL}/recommendations/{customer_id}` (or mock fallback if unset). Request is `GET` only — no headers beyond what `fetch` defaults add. Response is JSON: `{green, cheapest}` on 200, `{error}` on non-200.
- **Downstream:** Phase 5 persona rehearsal depends on `npm run build` producing a working `ui/dist/` that runs cleanly under `vite preview` against the deployed API. Phase 4 ships this (D-07). Phase 5 may additionally add S3+CloudFront hosting — out of scope for Phase 4.
- **Starter scaffold cleanup:** The current `ui/src/App.tsx` / `App.css` / `ui/src/assets/` contents are the default Vite+React starter (hero image, counter button, Vite/React link cards) and MUST be replaced (D-15).

</code_context>

<specifics>
## Specific Ideas

- **Equal-cards contract is the load-bearing decision from UI-SPEC — do not dilute it with tests, copy, or visual weight.** REC-03 says neither track is ranked above the other. UI-SPEC color contract enforces this. Tests don't need to duplicate it; code review does.
- **Mock fixture values must be demo-coherent.** If mock mode is active, all 3 personas MUST return savings that match DEMO-02's engineered story (Green ≈ $30/mo, Cheapest ≈ $55/mo on the flagship persona). Any drift between mock output and Phase 1 engineered output breaks the narrative if the demo falls back to mock mid-presentation.
- **Placeholder drift fix (D-11) is a real spec amendment, not a code-only workaround.** The UI-SPEC file at `04-UI-SPEC.md:109` must be edited to `e.g. CUST-001234`. This is a small planner task, logged so the spec and code stay in sync.
- **Quick-pick chips are presenter-safety, not a permanent feature.** They exist because the demo is live and typed IDs are risky. If Phase 5 rehearsal shows they're distracting or the client wants a "cleaner" screenshot, they can be hidden behind a feature flag later. For now: visible, no gate.
- **Card order is stable.** UI-SPEC: Green first, Cheapest second. Operator memory / repeated demo performance depends on this. Do not sort dynamically by savings or plan_id.
- **No scroll during a live call.** UI-01 is literal — at 1280px viewport both cards and the input form must be visible simultaneously. The planner's layout check is: "With Chrome DevTools set to 1280×800 (typical laptop minus browser chrome), is everything visible?" If not, adjust spacing before declaring victory.

</specifics>

<deferred>
## Deferred Ideas

- **S3 + CloudFront UI hosting** — Phase 5, only if the demo narrative requires a shareable URL. Would add a `UiHostingStack` CDK stack, a deploy pipeline, and origin-pinning CORS decisions on the Phase 3 API.
- **UI-03 call-script snippet card** — v2 (already in PROJECT.md Out of Scope for v1).
- **UI-04 usage narrative card** — v2 (already in PROJECT.md Out of Scope for v1).
- **Playwright end-to-end smoke** — considered and rejected for Phase 4 (D-14). Phase 5 persona rehearsal provides the end-to-end verification layer. Could be added in a later milestone if UI complexity grows.
- **Component-level RTL tests for card rendering** — considered and rejected (D-14). UI-SPEC locks all copy; RTL tests for string equality duplicate the spec.
- **Sentry / LogRocket / client-side observability** — not needed for a dummy-data demo; `console.error` is sufficient.
- **Cold-start pre-warm** — DEMO-03, already v2-deferred in PROJECT.md. Phase 4 accepts the skeleton + plain 504-if-it-times-out behavior.
- **Alt+D hidden-chip affordance** — considered and rejected; visible chips are clearer and honest about being a dummy-data demo.
- **`/personas` backend endpoint** — considered and rejected (D-09); would be scope creep into Phase 3. Hardcoded constant is sufficient.
- **Custom domain / branded URL** — Phase 5 if needed, otherwise never for the demo.
- **Mobile / responsive layout beyond UI-SPEC's <768px stack fallback** — already Out of Scope in REQUIREMENTS.md.

</deferred>

---

*Phase: 04-agent-assist-ui*
*Context gathered: 2026-04-24*
