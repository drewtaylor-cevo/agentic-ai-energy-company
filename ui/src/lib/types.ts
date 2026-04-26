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

export interface RecommendationResponse {
  green: TrackInfo;
  cheapest: TrackInfo;
}

// Matches api_lambda/handler.py::_error body shape (lines 46-52).
// The UI parses `response.status` first and only reads this body defensively —
// the UI-SPEC copy is used verbatim, not the server's `error` string.
export interface ApiError {
  error: string;
}
