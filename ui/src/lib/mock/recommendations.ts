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
//
// Phase 8 D-19: usage_narrative and call_script strings on each track are
// copied VERBATIM (byte-for-byte) from agent/narrative/fallbacks.py. If
// fallbacks.py changes, update this file in the same commit — same
// discipline as the savings numbers above. No auto-sync script (D-20).
export const MOCK_RECOMMENDATIONS: Record<string, RecommendationResponse> = {
  'CUST-001': {
    green: {
      plan_id: 'ECO',
      plan_name: 'EcoFlex 100',
      saving_monthly: 30.00,
      saving_annual: 360.00,
      usage_narrative: 'Strong cool-season usage with a family-sized load across the year.',
      call_script: 'Ask about EcoFlex — it suits a strong winter-heating profile like yours.',
    },
    cheapest: {
      plan_id: 'VAL',
      plan_name: 'Value 12',
      saving_monthly: 55.00,
      saving_annual: 660.00,
      usage_narrative: 'Consistently high household consumption with cool-season peaks.',
      call_script: 'Bring up Value Twelve — a budget-first pick for a high-usage home.',
    },
  },
  'CUST-002': {
    green: {
      plan_id: 'ECO',
      plan_name: 'EcoFlex 100',
      saving_monthly: 16.90,
      saving_annual: 202.80,
      usage_narrative: 'Mid-range apartment usage with gentle seasonal variation across the year.',
      call_script: 'Ask about EcoFlex — a steady, eco-aligned option for a mid-range home.',
    },
    cheapest: {
      plan_id: 'VAL',
      plan_name: 'Value 12',
      saving_monthly: 30.98,
      saving_annual: 371.76,
      usage_narrative: 'Moderate apartment consumption with only mild cool-season lifts.',
      call_script: 'Bring up Value Twelve — a cost-led pick for a mid-range apartment.',
    },
  },
  'CUST-003': {
    green: {
      plan_id: 'ECO',
      plan_name: 'EcoFlex 100',
      saving_monthly: 14.00,
      saving_annual: 168.00,
      usage_narrative: 'Summer-peak household profile with cooling-driven demand in warm months.',
      call_script: 'Ask about EcoFlex — an eco-aligned fit for a summer-peak cooling load.',
    },
    cheapest: {
      plan_id: 'VAL',
      plan_name: 'Value 12',
      saving_monthly: 25.67,
      saving_annual: 308.04,
      usage_narrative: 'Warm-season heavy with light winter usage and a cooling-led pattern.',
      call_script: 'Bring up Value Twelve — a cost-led option for a warm-season household.',
    },
  },
};
