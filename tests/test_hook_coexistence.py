"""Unit tests for hook coexistence — StreamingTraceHook + FourToolCapHook.

Verifies that both hooks can register for AfterToolCallEvent independently,
that StreamingTraceHook.reset() clears the callback, and that FourToolCapHook
budget enforcement is unaffected by StreamingTraceHook presence.

**Validates: Requirements 3.4**
"""
from __future__ import annotations

from unittest.mock import MagicMock

from strands.hooks import AfterToolCallEvent, HookRegistry

from agent.hooks.four_tool_cap import FourToolCapHook
from agent.hooks.streaming_trace import StreamingTraceHook


class TestBothHooksRegisterIndependently:
    """Both hooks register for AfterToolCallEvent independently."""

    def test_both_hooks_register_on_same_registry(self) -> None:
        """Both hooks can register callbacks on the same HookRegistry."""
        registry = HookRegistry()
        streaming_hook = StreamingTraceHook()
        cap_hook = FourToolCapHook(budget=8)

        streaming_hook.register_hooks(registry)
        cap_hook.register_hooks(registry)

        # Both should have registered — registry should have callbacks for AfterToolCallEvent
        assert registry.has_callbacks()
        callbacks = list(registry._registered_callbacks.get(AfterToolCallEvent, []))
        assert len(callbacks) == 2

    def test_registration_order_does_not_matter(self) -> None:
        """Registering in either order results in both callbacks present."""
        registry = HookRegistry()
        streaming_hook = StreamingTraceHook()
        cap_hook = FourToolCapHook(budget=8)

        # Register cap first, then streaming
        cap_hook.register_hooks(registry)
        streaming_hook.register_hooks(registry)

        callbacks = list(registry._registered_callbacks.get(AfterToolCallEvent, []))
        assert len(callbacks) == 2

    def test_both_callbacks_invoked_on_event(self) -> None:
        """When an AfterToolCallEvent fires, both hooks' callbacks are invoked."""
        registry = HookRegistry()
        streaming_hook = StreamingTraceHook()
        cap_hook = FourToolCapHook(budget=8)

        # Set up streaming callback to capture calls
        captured = []
        streaming_hook.set_callback(lambda name, summary: captured.append((name, summary)))

        streaming_hook.register_hooks(registry)
        cap_hook.register_hooks(registry)

        # Create a mock event for a known tool
        event = MagicMock(spec=[])
        event.tool_name = "detect_bill_shock"
        event.tool_result = {
            "is_shock": True,
            "delta_dollars": 65.16,
            "shock_month": "2025-10",
            "current_dollars": 167.88,
            "mean_dollars": 102.72,
        }
        event.agent = MagicMock()
        # Make it look like an AfterToolCallEvent for the registry
        event.__class__ = AfterToolCallEvent

        # Invoke all callbacks registered for this event type
        callbacks = list(registry._registered_callbacks.get(AfterToolCallEvent, []))
        for cb in callbacks:
            cb(event)

        # StreamingTraceHook should have fired its callback
        assert len(captured) == 1
        assert captured[0][0] == "detect_bill_shock"

        # FourToolCapHook should have incremented its counter
        assert cap_hook.used == 1


class TestStreamingTraceHookReset:
    """StreamingTraceHook.reset() clears the callback."""

    def test_reset_clears_callback(self) -> None:
        """After reset(), the internal callback is None."""
        hook = StreamingTraceHook()
        hook.set_callback(lambda name, summary: None)

        # Callback is set
        assert hook._callback is not None

        hook.reset()

        # Callback is cleared
        assert hook._callback is None

    def test_reset_prevents_callback_invocation(self) -> None:
        """After reset(), known tool events do not invoke the (now-cleared) callback."""
        hook = StreamingTraceHook()
        captured = []
        hook.set_callback(lambda name, summary: captured.append((name, summary)))

        hook.reset()

        # Fire a known tool event — callback should NOT be invoked
        event = MagicMock()
        event.tool_name = "get_billing_history"
        event.tool_result = [
            {"month": "2025-01", "amount": 100.0},
            {"month": "2025-02", "amount": 110.0},
        ]

        hook._on_tool_complete(event)

        assert len(captured) == 0

    def test_set_callback_after_reset_works(self) -> None:
        """A new callback can be set after reset() and will be invoked."""
        hook = StreamingTraceHook()

        # First callback
        first_captured = []
        hook.set_callback(lambda name, summary: first_captured.append((name, summary)))
        hook.reset()

        # Second callback
        second_captured = []
        hook.set_callback(lambda name, summary: second_captured.append((name, summary)))

        event = MagicMock()
        event.tool_name = "get_hardship_flag"
        event.tool_result = {"hardship_flag": True}

        hook._on_tool_complete(event)

        assert len(first_captured) == 0
        assert len(second_captured) == 1


class TestFourToolCapUnaffectedByStreamingHook:
    """FourToolCapHook budget enforcement is unaffected by StreamingTraceHook presence."""

    def test_budget_enforcement_with_streaming_hook_present(self) -> None:
        """FourToolCapHook still cancels the agent at budget limit when StreamingTraceHook is registered."""
        registry = HookRegistry()
        streaming_hook = StreamingTraceHook()
        cap_hook = FourToolCapHook(budget=8)

        streaming_hook.set_callback(lambda name, summary: None)

        streaming_hook.register_hooks(registry)
        cap_hook.register_hooks(registry)

        mock_agent = MagicMock()

        # Fire 8 tool events — budget should be exhausted on the 8th
        for i in range(8):
            event = MagicMock()
            event.tool_name = "simulate_savings"
            event.tool_result = {
                "green": {"saving_monthly": 14.0},
                "cheapest": {"saving_monthly": 25.67},
            }
            event.agent = mock_agent

            # Invoke all registered callbacks
            callbacks = list(registry._registered_callbacks.get(AfterToolCallEvent, []))
            for cb in callbacks:
                cb(event)

        # FourToolCapHook should have counted all 8 and cancelled
        assert cap_hook.used == 8
        mock_agent.cancel.assert_called_once()

    def test_budget_count_independent_of_streaming_callback(self) -> None:
        """FourToolCapHook counts all tool calls regardless of whether StreamingTraceHook skips them."""
        registry = HookRegistry()
        streaming_hook = StreamingTraceHook()
        cap_hook = FourToolCapHook(budget=8)

        captured = []
        streaming_hook.set_callback(lambda name, summary: captured.append((name, summary)))

        streaming_hook.register_hooks(registry)
        cap_hook.register_hooks(registry)

        mock_agent = MagicMock()

        # Fire events with UNKNOWN tool names — StreamingTraceHook skips them,
        # but FourToolCapHook should still count them.
        for i in range(8):
            event = MagicMock()
            event.tool_name = "unknown_tool"
            event.tool_result = {}
            event.agent = mock_agent

            callbacks = list(registry._registered_callbacks.get(AfterToolCallEvent, []))
            for cb in callbacks:
                cb(event)

        # StreamingTraceHook should NOT have fired (unknown tools)
        assert len(captured) == 0

        # FourToolCapHook should still have counted all 8 and cancelled
        assert cap_hook.used == 8
        mock_agent.cancel.assert_called_once()

    def test_streaming_hook_reset_does_not_affect_cap_hook(self) -> None:
        """Resetting StreamingTraceHook does not reset FourToolCapHook counter."""
        streaming_hook = StreamingTraceHook()
        cap_hook = FourToolCapHook(budget=8)

        streaming_hook.set_callback(lambda name, summary: None)

        # Simulate 2 tool calls on the cap hook
        mock_agent = MagicMock()
        event = MagicMock()
        event.agent = mock_agent
        cap_hook.on_tool_complete(event)
        cap_hook.on_tool_complete(event)

        assert cap_hook.used == 2

        # Reset streaming hook — cap hook should be unaffected
        streaming_hook.reset()

        assert cap_hook.used == 2
        assert streaming_hook._callback is None
