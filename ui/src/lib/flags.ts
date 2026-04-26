// Runtime feature flag (UI-06, D-09–D-13): the URL query parameter
// `?narrative=off` suppresses the v2.0 usage-narrative + call-script rows
// (AND their skeleton placeholders, D-10) so the UI collapses to its v1.0
// shape without a redeploy. Evaluated exactly once at module load — no
// React state, no context, no hook (D-12). Case-sensitive match on the
// literal "off" (D-13). URL is the sole source of truth — no
// localStorage/sessionStorage (D-11).
export const NARRATIVE_ENABLED =
  new URLSearchParams(window.location.search).get('narrative') !== 'off';
