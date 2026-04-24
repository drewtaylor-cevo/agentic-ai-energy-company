import type { RecommendationResponse } from '../types';

// Values ported from tests/conftest.py:47-100 (mock_savings_response,
// mock_marcus_response, mock_elena_response). These MUST stay in sync with the
// deterministic output of lambda/handler.py::simulate_savings_pure for each
// persona (verified in tests/test_simulate_savings.py).
//
// DEMO-02 flagship: CUST-001 (Sarah) Green ~$30/mo, Cheapest ~$55/mo — these
// numbers are load-bearing for the demo narrative. If the backend savings
// formula changes, update both this map AND the Python fixtures in the same
// commit.
//
// Plan IDs are always `ECO` (green) and `VAL` (cheapest) across all personas —
// the backend invariant asserted by tests/test_agent_smoke.py:81-85.
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
