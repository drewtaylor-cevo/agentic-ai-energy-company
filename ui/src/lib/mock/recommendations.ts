import type { ReasoningTraceEntry, RecommendationResponse, HardshipResponse } from '../types';

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
//
// Phase 13 D-29: reasoning_trace entries below MUST stay in sync with
// `agent/reasoning/summaries.py` formatters. Elena CUST-003 is the designated
// bill-shock persona (A-01 amendment); CUST-001/CUST-002 have empty traces.
// Run `npm run test` + `pytest tests/test_bill_shock_flow.py::TestCrossPersonaCanary`
// in the same commit when these values change.

// Phase 13: byte-exact trace for Elena (CUST-003), the designated bill-shock
// persona. Tool order follows the preference graph in _BASE_SYSTEM_PROMPT:
//   1. get_hardship_flag — evidence check
//   2. detect_bill_shock — optional anomaly confirmation
//   3. simulate_savings — ALWAYS last (REC-03)
//
// SUMMARIES MUST MATCH agent/reasoning/summaries.py OUTPUT EXACTLY.
// See `.planning/phases/13-*/13-01-SUMMARY.md` + 13-05-SUMMARY.md for Elena's
// measured pure-helper output (delta $65.16, mean $102.72, current $167.88,
// 2025-10 shock month). Byte-verified via:
//   python3 -c "from agent.reasoning.summaries import summary_detect_bill_shock;
//               from lambda.handler import detect_bill_shock_pure;
//               from infrastructure.seed_data.billing_records import ELENA_VASQUEZ_RECORDS;
//               print(summary_detect_bill_shock(detect_bill_shock_pure(ELENA_VASQUEZ_RECORDS)))"
export const MOCK_REASONING_TRACE_CUST003: ReasoningTraceEntry[] = [
  { tool: 'get_hardship_flag', summary: 'hardship_flag=False' },
  {
    tool: 'detect_bill_shock',
    summary:
      'Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)',
  },
  {
    tool: 'simulate_savings',
    // Elena's byte-exact Phase 11 D-13 fixtures: green $14.00/mo, cheapest $25.67/mo.
    summary: 'Green $14.00/mo; Cheapest $25.67/mo',
  },
];

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
    reasoning_trace: [],
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
    reasoning_trace: [],
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
    reasoning_trace: MOCK_REASONING_TRACE_CUST003,
  },
};


// Phase 14 AGENT-02: hardship mock responses.
// CUST-006 is the hardship persona — hardship_flag: true in DynamoDB PROFILE row.
// Strings MUST match agent/narrative/fallbacks.py CUST-006 hardship track byte-exact.
export const MOCK_HARDSHIP_RESPONSES: Record<string, HardshipResponse> = {
  'CUST-006': {
    kind: 'hardship',
    customer_id: 'CUST-006',
    reason: 'This customer account is flagged for dedicated support from our specialist team.',
    routing_target: 'hardship_team',
    call_script: 'Let me connect you with our specialist support team who can best help with your account.',
  },
};
