// Mirrors agent/agent.py::TrackInfo (lines 32-37) and ::RecommendationResponse (lines 40-43).
// Field names are snake_case to match the JSON wire format — do NOT camelCase.
// If the backend schema changes, update this file in the same commit.
// Phase 8 D-18: usage_narrative and call_script are required (not optional) — Phase 6 guarantees non-empty via per-field fallback; Phase 7 passes through verbatim.
export interface TrackInfo {
  plan_id: string;
  plan_name: string;
  saving_monthly: number;
  saving_annual: number;
  usage_narrative: string;
  call_script: string;
}

// Phase 13 D-07: one entry in the reasoning_trace surface.
// D-11 EXEMPTION: summary INTENTIONALLY contains digits, $, dates, %.
// Backend formatters live in agent/reasoning/summaries.py — keep byte-sync.
export interface ReasoningTraceEntry {
  tool: string;
  summary: string;
}

export interface RecommendationResponse {
  kind?: 'recommendation';
  green: TrackInfo;
  cheapest: TrackInfo;
  // Phase 13 D-07 — optional: empty/omitted on single-tool turns (CUST-001/004/005).
  // PUBLIC field; NOT stripped by api_lambda/handler.py (D-12).
  reasoning_trace?: ReasoningTraceEntry[];
  // Agentic Actions Portfolio — optional list of pending confirmable actions.
  // Empty/omitted when action preparation fails (D-04) or no actions applicable.
  pending_actions?: ConfirmableAction[];
}

// Phase 14 AGENT-02: hardship short-circuit response.
// Returned when hardship_flag is true — no green/cheapest tracks, no plan IDs.
// D-15 validated: reason + call_script contain no digits, currency, or banned terms.
export interface HardshipResponse {
  kind: 'hardship';
  customer_id: string;
  reason: string;
  routing_target: string;
  call_script: string;
}

// Phase 15 WF-01: follow-up email response.
// Returned when the rep clicks "Draft follow-up email" after a recommendation.
// D-15 extended: subject + body contain no digits, currency, or banned terms.
export interface FollowUpEmailResponse {
  kind: 'follow_up';
  customer_id: string;
  subject: string;
  body: string;
  plan_reference: string;
}

// Discriminated union for the API response — either a recommendation or hardship.
export type ApiResponse = RecommendationResponse | HardshipResponse;

// Type guard for hardship responses.
export function isHardshipResponse(data: ApiResponse): data is HardshipResponse {
  return (data as HardshipResponse).kind === 'hardship';
}

// SSE wire protocol event data shapes (streaming reasoning trace).
// Matches design.md §Wire Protocol Events — trace_step and error event payloads.
export interface TraceStepEvent {
  tool: string;
  summary: string;
}

export interface StreamingErrorEvent {
  status: number;
  message: string;
}

// Matches api_lambda/handler.py::_error body shape (lines 46-52).
// The UI parses `response.status` first and only reads this body defensively —
// the UI-SPEC copy is used verbatim, not the server's `error` string.
export interface ApiError {
  error: string;
}

// Retention Queue types — mirrors design.md §Risk_Signal and GET /retention-queue response.
// Wire format uses snake_case to match backend JSON — do NOT camelCase.
export interface RiskSignal {
  customer_id: string;
  risk_score: number;
  risk_summary: string;
  bill_shock_detected: boolean;
  usage_trend: 'increasing' | 'decreasing' | 'stable';
  hardship_flag: boolean;
}

export interface RetentionQueueResponse {
  customers_at_risk: number;
  queue: RiskSignal[];
}

// Agentic Actions Portfolio types — mirrors design.md §Confirmable_Action.
// Wire format uses snake_case to match backend JSON — do NOT camelCase.
export interface ConfirmableAction {
  action_id: string;
  action_type: 'tariff_switch' | 'send_sms' | 'payment_plan_offer';
  customer_id: string;
  payload: Record<string, unknown>;
  status: 'pending' | 'confirmed' | 'rejected';
}

// Conversational chat layer types — mirrors design.md §Data Models.
// Wire format uses snake_case to match backend JSON — do NOT camelCase.

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  reply: string;
  reasoning_trace: ReasoningTraceEntry[];
  session_id: string;
  customer_id: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  reasoning_trace?: ReasoningTraceEntry[];
  timestamp: number;
}
