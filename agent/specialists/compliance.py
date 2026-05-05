"""ComplianceReviewer — deterministic compliance gate.

Five AER NECF-aligned checks implemented as pure Python functions over
the response dict. No LLM call, no network I/O, no Agent, no BedrockModel.
Adds microseconds, not seconds.

Rules:
  1. Reference-period disclosure (Req 4.1): reasoning_trace must contain
     a get_billing_history or simulate_savings entry.
  2. No upsell-to-disadvantage (Req 4.2): saving_monthly >= 0 on both
     green and cheapest tracks.
  3. Hardship-flag cross-check (Req 4.3): kind: "hardship" responses must
     not contain plan_id, saving_monthly, or saving_annual at any level.
  4. Hardship category tool restriction (Req 4.4): reasoning_trace tools
     must be within the category's permitted_tools set.
  5. Family violence no financial content (Req 4.5): family_violence
     responses must contain zero financial terminology in reason,
     call_script, and permitted_actions.

Satisfies the AgentRole Protocol (handle(payload) -> dict).

Bi-mode import: try container /app/ layout first, fall back to repo layout.
"""
from __future__ import annotations

import string
from datetime import datetime, timezone
from typing import Any

# Bi-mode import: ComplianceCheckResult and ComplianceReview live in roles.py.
try:
    from roles import ComplianceCheckResult, ComplianceReview  # type: ignore[import-not-found]
except ImportError:
    from agent.roles import ComplianceCheckResult, ComplianceReview

# Bi-mode import: HARDSHIP_CATEGORIES and FINANCIAL_TERMS from hardship_config.
try:
    from specialists.hardship_config import HARDSHIP_CATEGORIES, FINANCIAL_TERMS  # type: ignore[import-not-found]
except ImportError:
    from agent.specialists.hardship_config import HARDSHIP_CATEGORIES, FINANCIAL_TERMS

# Tariff fields that must NOT appear in hardship responses (Req 4.3).
_TARIFF_FIELDS = frozenset({"plan_id", "saving_monthly", "saving_annual"})


class ComplianceReviewer:
    """Deterministic compliance gate — no LLM, no network I/O."""

    def handle(self, payload: dict[str, Any]) -> dict[str, Any]:
        """AgentRole Protocol entry point — wraps review().

        Not used directly by the Supervisor (which calls review()), but
        present so ComplianceReviewer satisfies the AgentRole Protocol.
        """
        review = self.review(
            payload.get("response", {}),
            payload.get("context", {}),
        )
        return review.model_dump()

    def review(
        self, response: dict, customer_context: dict
    ) -> ComplianceReview:
        """Run all applicable compliance checks on a specialist response."""
        checks: list[ComplianceCheckResult] = []
        kind = response.get("kind", "recommendation")

        if kind == "recommendation":
            checks.append(self._check_reference_period(response))
            checks.append(self._check_no_upsell_to_disadvantage(response))
        elif kind == "hardship":
            checks.append(self._check_hardship_no_tariff_data(response))
            checks.append(self._check_hardship_tool_restriction(response))
            category = response.get("category", "other")
            if category == "family_violence":
                checks.append(self._check_family_violence_no_financial(response))

        failures = [c.reason for c in checks if c.verdict == "fail"]
        return ComplianceReview(
            verdict="fail" if failures else "pass",
            rules_checked=[c.rule for c in checks],
            failures=failures,
            reviewed_at=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Rule 1: Reference-period disclosure (Req 4.1)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_reference_period(response: dict) -> ComplianceCheckResult:
        """Verify reasoning_trace contains a grounding tool entry.

        The response must contain at least one reasoning_trace entry with
        ``tool`` equal to ``"simulate_savings"`` or ``"get_billing_history"``
        — evidence that the recommendation is grounded in a specific billing
        period.
        """
        trace = response.get("reasoning_trace")
        if not trace or not isinstance(trace, list):
            return ComplianceCheckResult(
                rule="reference_period_disclosure",
                verdict="fail",
                reason="reasoning_trace is missing or empty — no billing-period grounding evidence",
            )

        grounding_tools = {"simulate_savings", "get_billing_history"}
        for entry in trace:
            if isinstance(entry, dict) and entry.get("tool") in grounding_tools:
                return ComplianceCheckResult(
                    rule="reference_period_disclosure",
                    verdict="pass",
                    reason="reasoning_trace contains billing-period grounding tool entry",
                )

        return ComplianceCheckResult(
            rule="reference_period_disclosure",
            verdict="fail",
            reason="reasoning_trace contains no simulate_savings or get_billing_history entry",
        )

    # ------------------------------------------------------------------
    # Rule 2: No upsell-to-disadvantage (Req 4.2)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_no_upsell_to_disadvantage(response: dict) -> ComplianceCheckResult:
        """Verify saving_monthly >= 0 on both green and cheapest tracks.

        A non-negative saving confirms the recommended plan does not
        increase costs compared to the customer's current arrangement.
        """
        offending_tracks: list[str] = []
        for track_name in ("green", "cheapest"):
            track = response.get(track_name)
            if isinstance(track, dict):
                saving = track.get("saving_monthly")
                if isinstance(saving, (int, float)) and saving < 0:
                    offending_tracks.append(track_name)

        if offending_tracks:
            tracks_str = " and ".join(offending_tracks)
            return ComplianceCheckResult(
                rule="no_upsell_to_disadvantage",
                verdict="fail",
                reason=f"negative saving_monthly on {tracks_str} track(s)",
            )

        return ComplianceCheckResult(
            rule="no_upsell_to_disadvantage",
            verdict="pass",
            reason="saving_monthly is non-negative on both tracks",
        )

    # ------------------------------------------------------------------
    # Rule 3: Hardship-flag cross-check (Req 4.3)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_hardship_no_tariff_data(response: dict) -> ComplianceCheckResult:
        """Verify no tariff fields leaked into a hardship response.

        Checks for plan_id, saving_monthly, and saving_annual at the
        top level AND nested within any sub-dict (recursive).
        """
        found = ComplianceReviewer._find_tariff_fields(response)
        if found:
            fields_str = ", ".join(sorted(found))
            return ComplianceCheckResult(
                rule="hardship_no_tariff_data",
                verdict="fail",
                reason=f"tariff field(s) found in hardship response: {fields_str}",
            )

        return ComplianceCheckResult(
            rule="hardship_no_tariff_data",
            verdict="pass",
            reason="no tariff data found in hardship response",
        )

    @staticmethod
    def _find_tariff_fields(obj: Any, _found: set[str] | None = None) -> set[str]:
        """Recursively search for tariff field keys in a dict structure."""
        if _found is None:
            _found = set()
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in _TARIFF_FIELDS:
                    _found.add(key)
                ComplianceReviewer._find_tariff_fields(value, _found)
        elif isinstance(obj, list):
            for item in obj:
                ComplianceReviewer._find_tariff_fields(item, _found)
        return _found

    # ------------------------------------------------------------------
    # Rule 4: Hardship category tool restriction (Req 4.4)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_hardship_tool_restriction(response: dict) -> ComplianceCheckResult:
        """Verify reasoning_trace tools are within category's permitted set.

        Each entry in reasoning_trace has a "tool" key. All tools must be
        within the category's permitted_tools frozenset from HARDSHIP_CATEGORIES.
        """
        category = response.get("category", "other")
        config = HARDSHIP_CATEGORIES.get(category, HARDSHIP_CATEGORIES["other"])
        permitted = config["permitted_tools"]

        trace = response.get("reasoning_trace", [])
        if not isinstance(trace, list):
            trace = []

        violations: list[str] = []
        for entry in trace:
            if isinstance(entry, dict):
                tool = entry.get("tool")
                if tool and tool not in permitted:
                    violations.append(tool)

        if violations:
            tools_str = ", ".join(sorted(set(violations)))
            return ComplianceCheckResult(
                rule="hardship_category_tool_restriction",
                verdict="fail",
                reason=f"tool(s) outside permitted set for {category}: {tools_str}",
            )

        return ComplianceCheckResult(
            rule="hardship_category_tool_restriction",
            verdict="pass",
            reason=f"all reasoning_trace tools within permitted set for {category}",
        )

    # ------------------------------------------------------------------
    # Rule 5: Family violence no financial content (Req 4.5)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_family_violence_no_financial(response: dict) -> ComplianceCheckResult:
        """Verify family_violence responses contain no financial terminology.

        Tokenizes reason, call_script, and str(permitted_actions) by splitting
        on whitespace and stripping punctuation, then checks each token against
        FINANCIAL_TERMS.
        """
        reason = response.get("reason", "")
        call_script = response.get("call_script", "")
        permitted_actions = response.get("permitted_actions", [])

        combined = f"{reason} {call_script} {str(permitted_actions)}"

        # Tokenize: split on whitespace, strip punctuation, lowercase
        tokens = [
            word.strip(string.punctuation).lower()
            for word in combined.split()
        ]

        found_terms: set[str] = set()
        for token in tokens:
            if token in FINANCIAL_TERMS:
                found_terms.add(token)

        if found_terms:
            terms_str = ", ".join(sorted(found_terms))
            return ComplianceCheckResult(
                rule="family_violence_no_financial_content",
                verdict="fail",
                reason=f"financial term(s) found in family_violence response: {terms_str}",
            )

        return ComplianceCheckResult(
            rule="family_violence_no_financial_content",
            verdict="pass",
            reason="no financial terminology in family_violence response",
        )
