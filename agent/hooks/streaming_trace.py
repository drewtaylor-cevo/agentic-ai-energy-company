"""Streaming reasoning trace hook — emits trace_step SSE events as tools complete.

Subscribes to AfterToolCallEvent and, for each known tool, computes a
deterministic summary via agent/reasoning/summaries.py and forwards it to
an injected callback. Unknown tools are silently skipped (Requirement 3.3).

Per-invocation lifecycle (SC-3 pattern, same as FourToolCapHook):
    _streaming_trace_hook.reset()       # clear callback
    _streaming_trace_hook.set_callback(cb)  # inject transport for this invocation
    agent_result = _agent(...)

The callback signature is ``cb(tool_name: str, summary: str)`` — the
transport layer (Lambda Response Streaming, test list-append, etc.) decides
how to serialise and flush.

Coexistence: this hook and FourToolCapHook both subscribe to
AfterToolCallEvent independently; Strands dispatches to all registered
callbacks in registration order.
"""
from __future__ import annotations

from typing import Callable, Optional

from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry

# Bi-mode import: agent/reasoning/ is COPYed to /app/reasoning/ by
# agent/Dockerfile; in the repo layout the module is
# agent/reasoning/summaries.py. Same precedent as four_tool_cap.py,
# narrative/, providers.py.
try:
    from reasoning.summaries import (
        summary_detect_bill_shock,
        summary_get_billing_history,
        summary_get_hardship_flag,
        summary_simulate_savings,
    )
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.reasoning.summaries import (
        summary_detect_bill_shock,
        summary_get_billing_history,
        summary_get_hardship_flag,
        summary_simulate_savings,
    )

_TRACE_TOOLS = frozenset({
    "detect_bill_shock",
    "get_billing_history",
    "get_hardship_flag",
    "simulate_savings",
})

_SUMMARY_DISPATCH = {
    "detect_bill_shock": summary_detect_bill_shock,
    "get_billing_history": summary_get_billing_history,
    "get_hardship_flag": summary_get_hardship_flag,
    "simulate_savings": summary_simulate_savings,
}


class StreamingTraceHook(HookProvider):
    """Emits trace_step events as tools complete (per-invocation lifecycle).

    Usage (in agent/agent.py):

        _streaming_trace_hook = StreamingTraceHook()
        _agent = Agent(
            ...,
            hooks=[_four_tool_cap, _streaming_trace_hook],
        )

        @app.entrypoint
        def invoke(payload):
            _four_tool_cap.reset()
            _streaming_trace_hook.reset()
            _streaming_trace_hook.set_callback(my_sse_writer)
            agent_result = _agent(...)
    """

    def __init__(self) -> None:
        self._callback: Optional[Callable[[str, str], None]] = None

    def set_callback(self, callback: Callable[[str, str], None]) -> None:
        """Inject the streaming callback for this invocation."""
        self._callback = callback

    def reset(self) -> None:
        """Clear per-invocation state. Called at the top of invoke()."""
        self._callback = None

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        """Strands API — subscribe to AfterToolCallEvent."""
        registry.add_callback(AfterToolCallEvent, self._on_tool_complete)

    def _on_tool_complete(self, event: AfterToolCallEvent) -> None:
        """Dispatch known tools to summary formatters; skip unknown tools."""
        tool_name = event.tool_name
        if tool_name not in _TRACE_TOOLS:
            return
        if self._callback is None:
            return
        formatter = _SUMMARY_DISPATCH[tool_name]
        summary = formatter(event.tool_result)
        self._callback(tool_name, summary)


__all__ = ["StreamingTraceHook"]
