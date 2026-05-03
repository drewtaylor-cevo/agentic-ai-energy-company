# Phase 14 Plan 04 Summary — UI HardshipBanner + mock fixture + ?narrative=off

**Status:** Complete
**Date:** 2026-05-03

## Changes

### ui/src/lib/types.ts
- Added `HardshipResponse` interface (`kind: "hardship"`, `customer_id`, `reason`, `routing_target`, `call_script`)
- Added `ApiResponse` discriminated union type (`RecommendationResponse | HardshipResponse`)
- Added `isHardshipResponse()` type guard
- Added optional `kind?: "recommendation"` to `RecommendationResponse` for discriminator

### ui/src/hooks/useRecommendations.ts
- New state variant: `{ status: 'hardship'; data: HardshipResponse; customerId: string }`
- Mock branch checks `MOCK_HARDSHIP_RESPONSES` before `MOCK_RECOMMENDATIONS`
- Real API branch uses `isHardshipResponse()` to route to hardship state

### ui/src/components/HardshipBanner.tsx (NEW)
- Dignity-preserving amber Alert with reason text, call script blockquote, routing target
- `?narrative=off` → renders null (LD-7 kill-switch)
- Accessible: `aria-label="Hardship support routing"` section landmark

### ui/src/App.tsx
- Added `HardshipBanner` import
- Added `state.status === 'hardship'` rendering branch between error and success

### ui/src/lib/mock/recommendations.ts
- Added `MOCK_HARDSHIP_RESPONSES` record with CUST-006 hardship data
- Strings byte-exact with `agent/narrative/fallbacks.py` CUST-006 hardship track

### ui/src/personas.ts
- Added CUST-006 persona chip: `CUST-006 · Hardship`

### ui/src/personas.test.ts
- Updated to expect 4 personas including CUST-006

### ui/src/components/HardshipBanner.test.tsx (NEW — 7 tests)
- Renders reason, call script (in blockquote), routing target, title
- Accessible section landmark
- No green/cheapest content leaked
- `?narrative=off` → renders null (vi.stubGlobal + resetModules pattern)

## Test results

- vitest: 103 passed, 0 failed (10 test files)
- tsc --noEmit: clean
