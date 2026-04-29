"""Phase 13 AGENT-01b — 4-tool cap via Strands HookProvider.

Amendment A-02 (RESEARCH §1): the Strands 1.37.0 Agent constructor has no
iteration-cap parameter. The cap is implemented as an AfterToolCallEvent
counter that cancels the agent via its cancel() API when the budget is
exhausted. The resulting stop_reason 'cancelled' is detected inside invoke()
and routed through the existing D-04 fallback path in agent/agent.py — so
HTTP 200 is always returned and REC-03's both-tracks contract holds via
FALLBACKS[customer_id] narrative stitching.

See CLAUDE.md Pitfall 2 addendum (Plan 09) for the regression tripwire.

State isolation: `self.used` is instance-level (not module-level). The
caller in `agent/agent.py::invoke()` is responsible for resetting `used=0`
before each invocation (via the `reset()` method below). SC-3 mirror —
module-level counters leak across invocations.
"""
from __future__ import annotations

from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry


class FourToolCapHook(HookProvider):
    """Per-invocation tool-call budget enforcer for AGENT-01b (D-14 amended).

    Usage (in agent/agent.py):

        _four_tool_cap = FourToolCapHook(budget=4)
        _agent = Agent(
            model=_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[simulate_savings, detect_bill_shock,
                   get_billing_history, get_hardship_flag],
            hooks=[_four_tool_cap],
        )

        @app.entrypoint
        def invoke(payload):
            _four_tool_cap.reset()  # IMPORTANT — clear per-invocation state.
            agent_result = _agent(...)
            if agent_result.stop_reason == "cancelled":
                raise RuntimeError("tool budget exhausted")
            ...

    The hook subscribes to one event type (tool-completion) and performs one
    action (increment + conditional cancel). No other event bindings.
    """

    def __init__(self, budget: int = 4) -> None:
        if budget < 1:
            raise ValueError("budget must be >= 1")
        self.budget: int = budget
        self.used: int = 0

    def reset(self) -> None:
        """Zero the per-invocation counter. Call from invoke() before _agent(...)."""
        self.used = 0

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        """Strands API — subscribe to AfterToolCallEvent."""
        registry.add_callback(AfterToolCallEvent, self.on_tool_complete)

    def on_tool_complete(self, event: AfterToolCallEvent) -> None:
        """Increment counter; cancel the agent when budget is exhausted.

        The agent-cancel call is the documented Strands mechanism — it sets
        an asyncio event that the event loop reads; post-cancellation the
        `agent_result.stop_reason` equals `'cancelled'` (verified via
        `typing.get_args(StopReason)` in RESEARCH §1).
        """
        self.used += 1
        if self.used >= self.budget:
            event.agent.cancel()


__all__ = ["FourToolCapHook"]
