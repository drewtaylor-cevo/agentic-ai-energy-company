# Phase 4: Agent-Assist UI — Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** 14 new files + 5 modified/replaced files + 1 spec amendment = 20
**Analogs found:** 12 cross-language mirrors + 3 in-repo stylistic references / 20 (5 greenfield)

> **Cross-language note:** No existing in-repo UI analog exists (ui/ is a fresh Vite scaffold). Most "analogs" here are **cross-language mirrors** — Python source-of-truth that the TypeScript code must reproduce exactly (regex, schema, error taxonomy, persona/savings values). A few are **greenfield** — no analog at all (shadcn init, Vite env wiring, useRecommendations hook). Each entry is tagged accordingly.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `ui/src/lib/api.ts` (types + fetch) | service | request-response | `agent/agent.py::RecommendationResponse` + `api_lambda/handler.py` | cross-language mirror (exact) |
| `ui/src/lib/validate.ts` (ID normalize + regex) | utility | transform | `lambda/handler.py::_validate_customer_id` (lines 39–52) | cross-language mirror (exact regex) |
| `ui/src/lib/errors.ts` (status→copy map) | utility | transform | `api_lambda/handler.py::_error` + UI-SPEC §Copywriting error table | cross-language mirror |
| `ui/src/hooks/useRecommendations.ts` | hook | request-response | none (greenfield) | greenfield |
| `ui/src/lib/mock/recommendations.ts` (fixture) | data | CRUD (read-only) | `tests/conftest.py::mock_savings_response` + `infrastructure/seed_data/billing_records.py` | cross-language mirror (exact values) |
| `ui/src/personas.ts` | config constant | — | `infrastructure/seed_data/billing_records.py` (CUST-001/002/003) | cross-language mirror |
| `ui/src/App.tsx` (rewritten per D-15) | component (page) | render | none — replaces starter; UI-SPEC §Interaction States is the contract | greenfield (spec-driven) |
| `ui/src/components/RecommendationCard.tsx` | component | render | none (greenfield; UI-SPEC §Color card-layout contract) | greenfield (spec-driven) |
| `ui/src/components/LookupForm.tsx` | component | event→request-response | none (greenfield; UI-SPEC §Copywriting form rows + D-10/D-11/D-12) | greenfield (spec-driven) |
| `ui/src/components/PersonaChips.tsx` | component | event | none (greenfield; D-08/D-09) | greenfield |
| `ui/src/components/ErrorAlert.tsx` | component | render | none (UI-SPEC §Color destructive + error copy table) | greenfield (spec-driven) |
| `ui/src/components/EmptyState.tsx` | component | render | none (UI-SPEC §Copywriting empty state rows) | greenfield (spec-driven) |
| `ui/src/components/RecommendationSkeletons.tsx` | component | render | none (UI-SPEC §Interaction States "Loading") | greenfield (spec-driven) |
| `ui/src/components/ui/*` (shadcn pulled blocks) | component | render | none — pulled from shadcn registry (button, input, card, label, skeleton, alert, badge) | external registry |
| `ui/src/hooks/useRecommendations.test.ts` | test | — | `tests/test_backend_api_handler.py` (parametrized status codes, mocked client) | cross-language mirror (stylistic) |
| `ui/src/lib/validate.test.ts` | test | — | `tests/test_backend_api_handler.py::test_invalid_customer_id_returns_400` parametrize | cross-language mirror (stylistic) |
| `ui/src/personas.test.ts` | test | — | `tests/test_simulate_savings.py::test_result_shape` (shape assertion) | cross-language mirror (stylistic) |
| `ui/.env.development`, `ui/.env.production` | config | — | none (greenfield Vite pattern) | greenfield |
| `ui/vite.config.ts` (add vitest + path alias) | config | — | `ui/vite.config.ts` existing (extend) | modify-existing |
| `ui/package.json` (add deps + test scripts) | config | — | `ui/package.json` existing (extend) | modify-existing |
| `ui/index.html` (title) | config | — | `ui/index.html` existing (modify `<title>ui</title>`) | modify-existing |
| `ui/src/App.css`, `ui/src/index.css` (replace) | config | — | delete starter; regenerate via shadcn init | delete + replace |
| `ui/src/assets/*` (remove starter images) | config | — | delete `react.svg`, `vite.svg`, `hero.png` | delete |
| `.planning/phases/04-agent-assist-ui/04-UI-SPEC.md` (amend L108 per D-11) | doc | — | self-reference | spec amendment |

---

## Pattern Assignments

### `ui/src/lib/api.ts` — TypeScript types + fetch (cross-language mirror)

**Analog:** `agent/agent.py::RecommendationResponse` (lines 32–43) + `api_lambda/handler.py` (lines 46–52, 102–106)

**Authoritative schema to mirror verbatim** — from `agent/agent.py:32-43`:

```python
class TrackInfo(BaseModel):
    plan_id: str = Field(description="Tariff plan identifier (e.g. ECO, VAL)")
    plan_name: str = Field(description="Human-readable plan name")
    saving_monthly: float = Field(description="Projected monthly saving in dollars")
    saving_annual: float = Field(description="Projected annual saving in dollars")


class RecommendationResponse(BaseModel):
    green: TrackInfo
    cheapest: TrackInfo
```

**TypeScript mirror (new file must reproduce exactly — field names, types, nesting):**

```typescript
// Mirrors agent/agent.py::TrackInfo and ::RecommendationResponse
export interface TrackInfo {
  plan_id: string;      // snake_case intentional — matches wire format
  plan_name: string;
  saving_monthly: number;
  saving_annual: number;
}

export interface RecommendationResponse {
  green: TrackInfo;
  cheapest: TrackInfo;
}

export interface ApiError {
  error: string;  // Matches api_lambda/handler.py::_error body shape
}
```

**Error response body shape** — from `api_lambda/handler.py:46-52`:

```python
def _error(status_code: int, message: str) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": message}),
    }
```

→ UI parses response with `response.status` FIRST, then `await response.json()` as either `RecommendationResponse` (200) or `{error: string}` (non-200). Never trust the body shape before checking status.

**Do not add fields not on `TrackInfo`.** UI-SPEC §Copywriting owns all presentation strings (methodology line, badge text, track heading) — those are NOT parsed from the API.

---

### `ui/src/lib/validate.ts` — Customer ID normalize + regex (cross-language mirror)

**Analog:** `lambda/handler.py::_validate_customer_id` (lines 39–52) + `api_lambda/handler.py:27`

**Canonical regex — DUPLICATED in two backend files, now a third time in UI** (per D-10 defense-in-depth):

```python
# lambda/handler.py line 39:
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")

# api_lambda/handler.py line 27 (identical, intentionally):
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")
```

**TypeScript mirror** — regex literal MUST match byte-for-byte:

```typescript
// Must match lambda/handler.py:39 and api_lambda/handler.py:27 exactly.
// If backend regex changes, this changes in lockstep. No divergence.
export const CUSTOMER_ID_PATTERN = /^CUST-\d{3,6}$/;
```

**Normalization rules (D-10):**
1. `trim()` — strip whitespace
2. `.toUpperCase()` — accept lowercase `cust-001`
3. Auto-insert dash: if input matches `^CUST\d{3,6}$` (no dash), insert `-` after `CUST`
4. Gate against `CUSTOMER_ID_PATTERN` — if it still doesn't match, show the 400 error copy from UI-SPEC (client-side, no fetch fires)

**Validation parametrize test seeds** — lift directly from `tests/test_backend_api_handler.py:70-73`:

```python
@pytest.mark.parametrize(
    "bad_id",
    ["NOTVALID", "cust-001", "CUST-1", "CUST-1234567", ""],
)
```

→ Vitest mirror: `describe.each(['NOTVALID', 'CUST-1', 'CUST-1234567', ''])` for post-normalize invalid cases. Note that `cust-001` should now be VALID after normalization (D-10 uppercases).

Additional positive cases to cover: `CUST001234` (no dash → normalizes to `CUST-001234`), `  CUST-001  ` (whitespace), `cust-001` (case), `CUST-001` (canonical).

---

### `ui/src/lib/errors.ts` — HTTP status → operator-facing copy (cross-language mirror)

**Analog:** `api_lambda/handler.py` error branches (lines 62–63, 80, 88, 91, 96–98) + UI-SPEC §Copywriting error table (lines 119–122)

**Backend error-status table** (api_lambda/handler.py):

| Status | Trigger | Server message |
|--------|---------|----------------|
| 400 | Regex mismatch (line 62–63) | "Invalid customer ID format. Use CUST-NNN (3-6 digits)." |
| 404 | No green/cheapest in body (line 96–98) | `f"Customer {customer_id} not found."` |
| 502 | `ClientError` (line 88) | "Recommendation service error. Please try again." |
| 504 | `ReadTimeoutError` (line 80) | "Recommendation service timed out. Please try again." |
| 500 | Unhandled `Exception` (line 91) | "Internal server error." |

**UI copy mapping** (UI-SPEC §Copywriting — UI does NOT show server `error` body to user; it shows spec-locked copy keyed by status):

```typescript
// Copy strings come from UI-SPEC, not from the API error body.
// The UI IGNORES response.json().error text and keys by status code only.
export function errorCopyForStatus(status: number, customerId: string): string {
  switch (status) {
    case 400:
      return "That doesn't look like a customer ID. Format is CUST followed by 3-6 digits.";
    case 404:
      return `No customer found for ${customerId}. Check the ID and try again.`;
    case 504:
      return "Recommendations are taking longer than expected. Try again in a moment.";
    case 500:
    case 502:
      return "Something went wrong on our end. Try again — if it persists, contact support.";
    default:
      // Network failure or unknown status — fall back to generic server copy
      return "Something went wrong on our end. Try again — if it persists, contact support.";
  }
}
```

**D-14 test surface:** parametrize over `[400, 404, 504, 502, 500, 0 (network)]` and assert copy strings match UI-SPEC exactly — mirrors `tests/test_backend_api_handler.py::test_invalid_customer_id_returns_400` parametrize style.

---

### `ui/src/hooks/useRecommendations.ts` — fetch hook (greenfield)

**Analog:** None in-repo. This is the primary greenfield surface for Phase 4.

**Greenfield shape (derived from D-01, D-03, D-04, D-14):**

```typescript
// Sketch — planner to refine.
type State =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: RecommendationResponse; customerId: string }
  | { status: 'error'; httpStatus: number; customerId: string };

export function useRecommendations() {
  const [state, setState] = useState<State>({ status: 'idle' });
  const abortRef = useRef<AbortController | null>(null);

  const lookup = useCallback(async (rawId: string) => {
    // 1. Cancel any in-flight request (re-query clears previous — UI-SPEC)
    abortRef.current?.abort();
    // 2. Normalize + validate (see ui/src/lib/validate.ts)
    const normalized = normalizeCustomerId(rawId);
    if (!CUSTOMER_ID_PATTERN.test(normalized)) {
      setState({ status: 'error', httpStatus: 400, customerId: normalized });
      return;
    }
    // 3. Clear previous results (UI-SPEC "Re-query" state)
    setState({ status: 'loading' });
    // 4. Branch: mock fallback if VITE_API_URL unset (D-03), else fetch
    const apiUrl = import.meta.env.VITE_API_URL;
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    try {
      const data = apiUrl
        ? await fetchFromApi(apiUrl, normalized, ctrl.signal)
        : await fetchFromMock(normalized);
      setState({ status: 'success', data, customerId: normalized });
    } catch (err) {
      if (err instanceof AbortError) return; // superseded
      const httpStatus = err instanceof HttpError ? err.status : 0;
      setState({ status: 'error', httpStatus, customerId: normalized });
    }
  }, []);

  return { state, lookup };
}
```

**Key behavioural requirements:**
- **No retry (D-04):** a single fetch per `lookup()` call. Operator re-submit triggers a new call.
- **AbortController for re-query (UI-SPEC "Re-query"):** previous in-flight request cancelled when a new lookup starts; stale data cleared to `loading` state before new request resolves.
- **Mock fallback (D-03):** when `import.meta.env.VITE_API_URL` is `undefined` or empty, read from `ui/src/lib/mock/recommendations.ts` keyed by normalized customer_id. Unknown IDs in mock mode still throw HttpError(404) so the error path is exercised.
- **Status-first parse (mirrors `api_lambda/handler.py` conventions):** `response.status` determines branch; body is parsed as `RecommendationResponse` only on 200. Non-200 body may be `{error: string}` but the UI discards it and uses spec copy.

---

### `ui/src/lib/mock/recommendations.ts` — Demo-coherent mock fixture (cross-language mirror)

**Analog:** `tests/conftest.py::mock_savings_response` (lines 47–62) + `tests/conftest.py::mock_marcus_response` (lines 66–81) + `tests/conftest.py::mock_elena_response` (lines 85–100)

**CRITICAL — these exact numbers MUST be reproduced** (D-03 "reconciled against seed_data … so mock output matches live API output exactly"):

```python
# tests/conftest.py lines 49-62 (flagship persona, DEMO-02 contract):
return {
    "green": {
        "plan_id": "ECO",
        "plan_name": "EcoFlex 100",
        "saving_monthly": 30.00,
        "saving_annual": 360.00,
    },
    "cheapest": {
        "plan_id": "VAL",
        "plan_name": "Value 12",
        "saving_monthly": 55.00,
        "saving_annual": 660.00,
    },
}
```

**TypeScript mirror (port verbatim — numbers are load-bearing for DEMO-02 narrative):**

```typescript
import type { RecommendationResponse } from '../api';

// Values ported from tests/conftest.py:47-100 (mock_savings_response,
// mock_marcus_response, mock_elena_response). These MUST stay in sync
// with the deterministic output of lambda/handler.py::simulate_savings_pure
// for each persona (verified in tests/test_simulate_savings.py).
// If backend savings formula changes, update both.
export const MOCK_RECOMMENDATIONS: Record<string, RecommendationResponse> = {
  'CUST-001': {
    green:    { plan_id: 'ECO', plan_name: 'EcoFlex 100', saving_monthly: 30.00, saving_annual: 360.00 },
    cheapest: { plan_id: 'VAL', plan_name: 'Value 12',    saving_monthly: 55.00, saving_annual: 660.00 },
  },
  'CUST-002': {
    green:    { plan_id: 'ECO', plan_name: 'EcoFlex 100', saving_monthly: 16.90, saving_annual: 202.80 },
    cheapest: { plan_id: 'VAL', plan_name: 'Value 12',    saving_monthly: 30.98, saving_annual: 371.76 },
  },
  'CUST-003': {
    green:    { plan_id: 'ECO', plan_name: 'EcoFlex 100', saving_monthly: 14.00, saving_annual: 168.00 },
    cheapest: { plan_id: 'VAL', plan_name: 'Value 12',    saving_monthly: 25.67, saving_annual: 308.04 },
  },
};
```

**Reconciliation checkpoints (for the planner's verification step):**
- Sarah (CUST-001) Green $30.00, Cheapest $55.00 — `infrastructure/seed_data/billing_records.py:6` + `test_simulate_savings.py:19-26` (DEMO-02 flagship, hard target).
- Marcus (CUST-002) Green $16.90, Cheapest $30.98 — `conftest.py:69-79`. Note: `test_simulate_savings.py:78` asserts `~$16.92 / ~$31.02` with a ±$0.10 tolerance; the conftest uses `16.90 / 30.98` as the mock canonical. Use the conftest values.
- Elena (CUST-003) Green $14.00, Cheapest $25.67 — `conftest.py:88-98`. Note: `test_simulate_savings.py:85` asserts `~$13.98 / ~$25.63`; use conftest values.
- Plan IDs are always `ECO` (green) + `VAL` (cheapest) — invariant from `tests/test_agent_smoke.py:81-85`.

Unknown customer_ids (anything not in the map) in mock mode MUST throw `HttpError(404)` so the error flow is demoable in mock mode.

---

### `ui/src/personas.ts` — Quick-pick chip labels (cross-language mirror)

**Analog:** `infrastructure/seed_data/billing_records.py` (lines 46–65)

**Persona identity & labels from Phase 1 seed data:**

```python
# billing_records.py:46 — Sarah Chen (CUST-001), high-usage family household
# billing_records.py:53 — Marcus Webb (CUST-002), mid-usage apartment dweller
# billing_records.py:60 — Elena Vasquez (CUST-003), seasonal-heavy
```

**TypeScript constant (D-09 shape `{id, label}`):**

```typescript
// Mirrors the 3 personas seeded by infrastructure/seed_data/billing_records.py.
// IDs MUST satisfy CUSTOMER_ID_PATTERN — asserted in personas.test.ts.
// Labels phrased as D-08: "CUST-NNN · <short-profile>" for one-click operator safety.
export interface Persona {
  id: string;     // canonical format CUST-NNN
  label: string;  // rendered on the chip
}

export const PERSONAS: readonly Persona[] = [
  { id: 'CUST-001', label: 'CUST-001 · High usage' },
  { id: 'CUST-002', label: 'CUST-002 · Mid usage' },
  { id: 'CUST-003', label: 'CUST-003 · Low usage' },
] as const;
```

**Test shape (D-14):** assert every `persona.id` passes `CUSTOMER_ID_PATTERN.test()`. Mirrors the shape-assertion style of `tests/test_simulate_savings.py:50-56`.

---

### `ui/src/App.tsx` — Page shell (greenfield, replaces starter per D-15)

**Analog:** None. Current `ui/src/App.tsx` is Vite+React starter (counter + hero logos, lines 1–122) and MUST be deleted in full (D-15). No pattern to copy — UI-SPEC §Interaction States lines 144–152 is the contract.

**Required composition:**
1. Page title "Tariff Recommendations" (UI-SPEC Display / 28px / semibold)
2. `<LookupForm>` — input + CTA (UI-SPEC §Copywriting form rows)
3. `<PersonaChips>` (D-08, below form, above results)
4. Result region — state-driven branch on `useRecommendations().state.status`:
   - `idle` → `<EmptyState>`
   - `loading` → `<RecommendationSkeletons>` (two equal-shape skeletons — UI-SPEC Interaction States "Loading")
   - `success` → `<RecommendationCard track="green" />` + `<RecommendationCard track="cheapest" />` (Green first, Cheapest second — UI-SPEC §Specifics "Card order is stable")
   - `error` → `<ErrorAlert>` IN PLACE OF cards (UI-SPEC §Interaction States "Error")

**Layout contract:** 1280px viewport, two cards side-by-side via grid/flex with `xl` (32px) gap between cards. Stacked vertically below 768px (UI-SPEC §Interaction States line 150).

**Forbidden additions (REC-03 / UI-SPEC §Color card-layout contract):**
- No visual weight differentiating one card from the other beyond accent color, heading text, icon, methodology line.
- No sorting cards dynamically by savings. Order is always Green, Cheapest.
- No "recommended" badge, "better value" label, or comparative ranking anywhere.

---

### `ui/src/components/RecommendationCard.tsx` — (greenfield)

**Analog:** None. UI-SPEC §Color lines 88–94 is the contract.

**Equal-cards contract (load-bearing — non-negotiable):** both card renders MUST share one component. The ONLY permitted differences are the 4 props listed in UI-SPEC §Color lines 89–92:

```typescript
interface RecommendationCardProps {
  track: 'green' | 'cheapest';  // drives accent color + icon + heading + methodology
  data: TrackInfo;              // from RecommendationResponse.green or .cheapest
}
```

Internal: a `TRACK_CONFIG` map keyed by `track` producing `{accent, icon, heading, badge, methodologyTemplate}` — all strings sourced from UI-SPEC §Copywriting lines 113–118, colors from UI-SPEC §Color lines 79–80.

Methodology templating rule from UI-SPEC §Copywriting lines 125–126: substitute `{plan_name}` from `data.plan_name`; fall back to `"selected"` if missing/empty.

---

### `ui/src/components/LookupForm.tsx` — (greenfield)

**Analog:** None. UI-SPEC §Copywriting rows 107–110 + D-10/D-11/D-12.

**Required behaviour (verbatim from decisions):**
- `<form onSubmit>` wrapper; CTA `type="submit"` (D-12). Enter and button click both submit.
- Input label "Customer ID", placeholder **`e.g. CUST-001234`** (D-11 amendment — NOT the UI-SPEC line 108 text which says `e.g. CUST001234`).
- CTA label "Look up customer" / "Looking up…" (UI-SPEC lines 109–110). CTA disabled when `state.status === 'loading'`.
- On submit: call `normalizeCustomerId(value)` → gate against `CUSTOMER_ID_PATTERN` → call `lookup()` if valid, else set error 400 state.

**Placeholder amendment (D-11) is a real spec edit:** `04-UI-SPEC.md` line 108 must be changed from `e.g. CUST001234` to `e.g. CUST-001234`. This is a planner task tracked separately from the component itself.

---

### `ui/src/components/PersonaChips.tsx` — (greenfield, D-08/D-09)

Reads `PERSONAS` from `ui/src/personas.ts`. Renders 3 chips; clicking a chip populates the `LookupForm` input and submits (or just populates — planner discretion, but D-08 "one click populates" suggests populate-only, operator clicks CTA to fire). Visible between form and empty state / results.

Uses shadcn `badge` primitive (UI-SPEC §Design System line 30 lists `badge` as an expected component).

---

### `ui/src/components/ErrorAlert.tsx` — (greenfield, UI-SPEC §Interaction States line 151)

shadcn `Alert` with `destructive` variant. Renders **in place of** result cards (not alongside). Copy keyed by HTTP status via `errorCopyForStatus(status, customerId)` from `ui/src/lib/errors.ts`.

Destructive color `#DC2626` (red-600) — UI-SPEC §Color line 82, border + icon only.

---

### `ui/src/components/EmptyState.tsx` — (greenfield, UI-SPEC §Copywriting lines 111–112)

Static. Heading: "No customer selected". Body: "Enter a customer ID to see tariff recommendations." Rendered when `state.status === 'idle'`.

---

### `ui/src/components/RecommendationSkeletons.tsx` — (greenfield, UI-SPEC §Interaction States "Loading")

Two `Skeleton` placeholders in the exact shape of the two `RecommendationCard` renders — same width, same height. Prevents layout shift during `loading → success` transition. Rendering logic must match the card's grid cells so switching between skeletons and cards does NOT cause reflow (manual verification step per D-07).

Optional (Claude discretion per CONTEXT.md "Cold-start reassurance copy"): a "Still looking…" hint after ~3s. Not a success criterion.

---

### `ui/src/hooks/useRecommendations.test.ts` — (cross-language stylistic mirror)

**Analog:** `tests/test_backend_api_handler.py` (entire file; lines 1–178)

**Pattern to reproduce — parametrized status tests with mocked client:**

Python version (lines 41–65, 107–149):

```python
@patch("api_lambda.handler._agentcore_client")
def test_valid_customer_success(mock_client, mock_savings_response):
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(mock_savings_response)
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 200

@patch("api_lambda.handler._agentcore_client")
def test_timeout_returns_504(mock_client):
    mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(...)
    result = handler(_make_event("CUST-001"), None)
    assert result["statusCode"] == 504
```

**Vitest mirror pattern:**

```typescript
// Vi mock of fetch, parametrized over status codes.
// Uses the same error taxonomy covered by test_backend_api_handler.py.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useRecommendations } from './useRecommendations';

beforeEach(() => vi.restoreAllMocks());

describe('useRecommendations', () => {
  it.each([
    [200, 'success'],
    [400, 'error'],
    [404, 'error'],
    [500, 'error'],
    [502, 'error'],
    [504, 'error'],
  ])('HTTP %i maps to %s state', async (httpStatus, expectedStatus) => {
    vi.stubGlobal('fetch', vi.fn(() =>
      Promise.resolve(new Response(
        httpStatus === 200 ? JSON.stringify(MOCK_RECOMMENDATIONS['CUST-001']) : '{"error":"x"}',
        { status: httpStatus }
      ))
    ));
    // ... renderHook + act + assert state ...
  });

  it('network failure maps to error state with httpStatus=0', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('network'))));
    // ...
  });

  it('falls back to mock fixture when VITE_API_URL is unset', async () => {
    vi.stubEnv('VITE_API_URL', '');
    // ...
  });
});
```

**Test surface (D-14):** success / 400 / 404 / 504 / 502 / 500 / network failure / mock fallback branch. No component-render tests (D-14 explicit exclusion).

---

### `ui/src/lib/validate.test.ts` — (cross-language stylistic mirror)

**Analog:** `tests/test_backend_api_handler.py::test_invalid_customer_id_returns_400` (lines 70–81)

Port the parametrize list verbatim, plus D-10 normalization positive cases:

```typescript
describe('normalizeCustomerId + CUSTOMER_ID_PATTERN', () => {
  // Normalization produces a canonical match:
  it.each([
    ['CUST-001',    'CUST-001'],
    ['cust-001',    'CUST-001'],
    ['  CUST-001 ', 'CUST-001'],
    ['CUST001234',  'CUST-001234'],  // dash auto-insert
  ])('normalizes "%s" → "%s" (canonical, passes regex)', (raw, expected) => {
    const normalized = normalizeCustomerId(raw);
    expect(normalized).toBe(expected);
    expect(CUSTOMER_ID_PATTERN.test(normalized)).toBe(true);
  });

  // Post-normalize still invalid — from tests/test_backend_api_handler.py:70-73:
  it.each(['NOTVALID', 'CUST-1', 'CUST-1234567', ''])(
    '"%s" fails regex after normalization',
    (bad) => {
      expect(CUSTOMER_ID_PATTERN.test(normalizeCustomerId(bad))).toBe(false);
    }
  );
});
```

---

### `ui/src/personas.test.ts` — (cross-language stylistic mirror)

**Analog:** `tests/test_simulate_savings.py::test_result_shape` (lines 50–56)

Shape-assertion pattern:

```typescript
import { describe, it, expect } from 'vitest';
import { PERSONAS } from './personas';
import { CUSTOMER_ID_PATTERN } from './lib/validate';

describe('PERSONAS', () => {
  it('has exactly 3 entries (matches Phase 1 seed data)', () => {
    expect(PERSONAS).toHaveLength(3);
  });

  it('all IDs satisfy CUSTOMER_ID_PATTERN', () => {
    for (const p of PERSONAS) {
      expect(CUSTOMER_ID_PATTERN.test(p.id)).toBe(true);
    }
  });

  it('IDs match the 3 seeded customers', () => {
    expect(PERSONAS.map(p => p.id)).toEqual(['CUST-001', 'CUST-002', 'CUST-003']);
  });
});
```

---

### `ui/vite.config.ts` — modify existing (extend)

**Analog:** existing `ui/vite.config.ts` (7 lines, minimal).

**Required extensions:**
1. Add `resolve.alias` for `@/*` if shadcn init hasn't already added it (shadcn init typically writes a `components.json` with path alias).
2. Add Vitest `test` config block (D-13): `environment: 'jsdom'`, `globals: true`, `setupFiles: ['./src/test-setup.ts']`.

```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
})
```

---

### `ui/package.json` — modify existing (add deps + scripts)

**Current deps (preserve):** react 19.2.5, react-dom 19.2.5, vite 8, typescript 6, eslint 10.

**Add (dev):** `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`, `@types/node` (already present).

**Add (runtime):** `lucide-react` (UI-SPEC §Design System line 25), plus whatever shadcn init adds (tailwindcss, class-variance-authority, clsx, tailwind-merge, `@radix-ui/*` per block pulled, `tailwindcss-animate`).

**Add scripts:** `"test": "vitest run"`, `"test:watch": "vitest"`.

Existing `build`: `"tsc -b && vite build"` is correct — preserve. `preview` script exists, satisfies D-07.

---

### `ui/.env.development`, `ui/.env.production` — greenfield (Vite pattern, D-02)

```ini
# .env.development (checked in — safe, holds dev API URL or empty for mock mode)
VITE_API_URL=
# Leave empty to exercise mock fallback during development (D-03).
# Set to the deployed API origin to test against a live backend.

# .env.production (checked in — holds demo-day API URL once Phase 5 deploys)
VITE_API_URL=
# Empty = mock mode (demo safety net).
# Set to deployed API URL for live-API demo build.
```

Vite reads `import.meta.env.VITE_API_URL` at build time only (D-02 "build-time env"); rebuild required to switch.

---

### `ui/index.html` — modify (title)

Current `<title>ui</title>` (line 7). Change to `<title>Tariff Recommendations</title>` per CONTEXT.md "Favicon / page title" (Claude's discretion).

Favicon: keep default `/favicon.svg` reference or replace with a neutral-slate utility icon (Claude discretion).

---

### `ui/src/App.css`, `ui/src/index.css` — replace

Current `index.css` (purple/accent `#aa3bff` theme, 112 lines) and `App.css` are Vite starter CSS and conflict with the shadcn New York/Slate theme. Delete both. `npx shadcn@latest init` regenerates `index.css` with the Slate CSS variables + Tailwind directives.

---

### `ui/src/assets/*` — delete starter images

Delete `ui/src/assets/hero.png`, `ui/src/assets/react.svg`, `ui/src/assets/vite.svg` (D-15). Any new assets (e.g., a utility icon) belong here with fresh filenames.

---

### `.planning/phases/04-agent-assist-ui/04-UI-SPEC.md` line 108 — spec amendment

**Current (line 108):** `| Form placeholder | e.g. CUST001234 |`

**Amended (per D-11):** `| Form placeholder | e.g. CUST-001234 |`

Tracked as a planner task (CONTEXT.md §Specifics: "Placeholder drift fix (D-11) is a real spec amendment, not a code-only workaround").

---

## Shared Patterns

### Cross-language wire-format contract (applies to `api.ts`, `mock/recommendations.ts`, `validate.ts`)

**Source of truth hierarchy:**
1. `agent/agent.py::RecommendationResponse` (lines 32–43) — per-track schema. TypeScript `TrackInfo` / `RecommendationResponse` interfaces mirror exactly.
2. `api_lambda/handler.py:27` + `lambda/handler.py:39` — regex `^CUST-\d{3,6}$`. TypeScript literal identical.
3. `api_lambda/handler.py::_error` (lines 46–52) — error body shape `{"error": "..."}`. UI parses by status code first, body second.
4. `tests/conftest.py` lines 47–100 — canonical per-persona savings values. Mock fixture ports verbatim.
5. `infrastructure/seed_data/billing_records.py` lines 46–65 — persona identity + usage profile labels.

**Rule:** if the backend regex, schema field names, types, or savings values change, every TypeScript mirror must be updated in lockstep within the same commit. Planner should call out drift risk in the plan's success criteria.

---

### Backend "offline unit + smoke" testing split (applies to D-14 test files)

**Source:** Phase 3 test layout — `tests/test_backend_api_handler.py` (offline unit, mocked client, no AWS) + `tests/test_backend_api_smoke.py` (live API, env-gated skipif, integration).

**UI analog:** Vitest unit tests for logic (D-14) + manual `vite preview` smoke at 1280px (D-07). No Vitest equivalent of live smoke — that's Phase 5 persona rehearsal.

**Stylistic conventions to carry forward:**
- Parametrize status codes / bad inputs (mirrors `@pytest.mark.parametrize` usage in `test_backend_api_handler.py:70-73`).
- Shape assertions over string-equality assertions where possible (mirrors `test_simulate_savings.py:50-56`).
- Unit tests must pass without env vars, mocks, or network (`test_backend_api_handler.py` mocks `_agentcore_client`; Vitest stubs `fetch`).

---

### Status-code-first response parsing (applies to `useRecommendations.ts`, `errors.ts`)

**Source:** `api_lambda/handler.py:46-52` — server returns a different body shape per status (success body = `{green, cheapest}`, error body = `{error}`). Parsing the body before checking status is a bug.

**UI pattern:**
```typescript
const response = await fetch(url, { signal });
if (!response.ok) {
  throw new HttpError(response.status);  // branch on status, not body
}
return await response.json() as RecommendationResponse;
```

The `response.json()` for non-200 MAY yield `{error: string}` but the UI discards it — operator-facing copy is owned by UI-SPEC, not the server.

---

## No Analog Found (pure greenfield)

| File | Role | Reason |
|------|------|--------|
| `ui/src/hooks/useRecommendations.ts` | hook | No hook exists in repo; no React code anywhere pre-Phase-4. Greenfield per D-01. |
| `ui/src/App.tsx` (post-rewrite) | page | Current file is starter to be deleted (D-15); spec-driven from UI-SPEC §Interaction States, no internal precedent. |
| `ui/src/components/*` (all 6 new components) | component | No component tree exists. Each is spec-driven from UI-SPEC sections, not code-driven. |
| `ui/src/components/ui/*` (shadcn blocks) | component | Pulled from external shadcn registry, not authored. Not a true "analog" search target. |
| `ui/.env.development` / `ui/.env.production` | config | Greenfield Vite env wiring. No precedent; standard Vite pattern. |

Planner should lean on UI-SPEC for all presentation decisions in these files, and on this PATTERNS.md (the shared-patterns section above) for wire-format, validation, and error-mapping contracts.

---

## Metadata

**Analog search scope:** `agent/`, `api_lambda/`, `lambda/`, `infrastructure/seed_data/`, `tests/`, `ui/` (scaffold inventory).
**Files scanned:** 16 (Python source 4, Python tests 4, Vite scaffold 8).
**Pattern extraction date:** 2026-04-24.
**Key observation:** Phase 4 is 80% spec-driven (UI-SPEC) and 20% backend-mirror. No useful in-repo UI analog exists; the load-bearing "analogs" are cross-language contracts (regex, schema, savings values) that MUST not drift from Python source.
