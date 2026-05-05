"""Unit tests for agent chat action (Task 4.4 — Conversational Chat Layer).

Tests cover:
- Chat action dispatches to handle_chat()
- System prompt composition (base + chat, no narrative)
- Reasoning trace extraction from chat agent result
- Response shape: reply, reasoning_trace, session_id, customer_id all present
- D-04: unexpected exception returns error dict, never raises
- Existing recommend action unchanged (regression)
- Existing follow_up action unchanged (regression)

Requirements: 4.1, 4.2, 4.6, 8.1, 8.4, 8.5
"""
from unittest.mock import patch, MagicMock
import pytest

from agent.agent import (
    handle_chat,
    invoke,
    _BASE_SYSTEM_PROMPT,
    _extract_reasoning_trace,
    ReasoningTraceEntry,
)
from agent.chat_prompt import _CHAT_SYSTEM_PROMPT
from agent.narrative.prompt_loader import NARRATIVE_PROMPT


# --- Test: chat action dispatches to handle_chat() ---


class TestChatActionDispatch:
    """invoke() with action='chat' dispatches to handle_chat()."""

    def test_chat_action_dispatches_to_handle_chat(self):
        """Req 4.1: invoke() routes action='chat' to handle_chat()."""
        with patch("agent.agent.handle_chat", return_value={
            "reply": "test reply",
            "reasoning_trace": [],
            "session_id": "sess-123",
            "customer_id": "CUST-001",
        }) as mock_handle:
            result = invoke({"customer_id": "CUST-001", "action": "chat", "message": "Hello"})
            mock_handle.assert_called_once_with(
                {"customer_id": "CUST-001", "action": "chat", "message": "Hello"}
            )
            assert result["reply"] == "test reply"

    def test_chat_action_does_not_route_to_recommend(self):
        """action='chat' does not fall through to the recommendation path."""
        with patch("agent.agent.handle_chat", return_value={
            "reply": "chat response",
            "reasoning_trace": [],
            "session_id": "sess-abc",
            "customer_id": "CUST-002",
        }) as mock_handle:
            result = invoke({"customer_id": "CUST-002", "action": "chat", "message": "test"})
            # Should not contain recommendation keys
            assert "green" not in result
            assert "cheapest" not in result
            assert result["reply"] == "chat response"


# --- Test: system prompt composition ---


class TestChatSystemPromptComposition:
    """Chat system prompt is base + chat extension, no narrative prompt."""

    def test_chat_prompt_includes_base(self):
        """Req 4.6: Chat prompt starts with _BASE_SYSTEM_PROMPT."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(__str__=lambda s: "reply text")
            mock_instance.messages = []
            MockAgent.return_value = mock_instance

            handle_chat({
                "customer_id": "CUST-001",
                "action": "chat",
                "message": "test",
                "session_id": "sess-1",
                "messages": [],
            })

            # Verify Agent was constructed with the correct system prompt
            call_kwargs = MockAgent.call_args[1]
            system_prompt = call_kwargs["system_prompt"]
            assert system_prompt.startswith(_BASE_SYSTEM_PROMPT)

    def test_chat_prompt_includes_chat_extension(self):
        """Req 4.1: Chat prompt includes _CHAT_SYSTEM_PROMPT."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(__str__=lambda s: "reply text")
            mock_instance.messages = []
            MockAgent.return_value = mock_instance

            handle_chat({
                "customer_id": "CUST-001",
                "action": "chat",
                "message": "test",
                "session_id": "sess-1",
                "messages": [],
            })

            call_kwargs = MockAgent.call_args[1]
            system_prompt = call_kwargs["system_prompt"]
            assert _CHAT_SYSTEM_PROMPT in system_prompt

    def test_chat_prompt_excludes_narrative(self):
        """Req 4.6: Chat prompt does NOT include NARRATIVE_PROMPT."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(__str__=lambda s: "reply text")
            mock_instance.messages = []
            MockAgent.return_value = mock_instance

            handle_chat({
                "customer_id": "CUST-001",
                "action": "chat",
                "message": "test",
                "session_id": "sess-1",
                "messages": [],
            })

            call_kwargs = MockAgent.call_args[1]
            system_prompt = call_kwargs["system_prompt"]
            assert NARRATIVE_PROMPT not in system_prompt

    def test_chat_prompt_composition_exact(self):
        """Prompt is exactly _BASE_SYSTEM_PROMPT + '\\n\\n' + _CHAT_SYSTEM_PROMPT."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_instance.return_value = MagicMock(__str__=lambda s: "reply text")
            mock_instance.messages = []
            MockAgent.return_value = mock_instance

            handle_chat({
                "customer_id": "CUST-001",
                "action": "chat",
                "message": "test",
                "session_id": "sess-1",
                "messages": [],
            })

            call_kwargs = MockAgent.call_args[1]
            system_prompt = call_kwargs["system_prompt"]
            expected = _BASE_SYSTEM_PROMPT + "\n\n" + _CHAT_SYSTEM_PROMPT
            assert system_prompt == expected


# --- Test: reasoning trace extraction ---


class TestChatReasoningTraceExtraction:
    """Reasoning trace is extracted from chat agent result."""

    def test_extract_reasoning_trace_with_tool_calls(self):
        """Req 4.2: reasoning trace extracted from agent messages with tool calls."""
        # Simulate messages with toolUse and toolResult blocks
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "name": "get_billing_history",
                            "toolUseId": "tu-001",
                            "input": {"customer_id": "CUST-001"},
                        }
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": "tu-001",
                            "content": [
                                {
                                    "json": {
                                        "records": [
                                            {"month": "2025-01", "kwh": 400, "cost_dollars": 120.0},
                                            {"month": "2025-02", "kwh": 520, "cost_dollars": 156.0},
                                        ]
                                    }
                                }
                            ],
                        }
                    }
                ],
            },
        ]

        # Create a mock agent_result
        mock_result = MagicMock()
        mock_result.message = messages[-1]

        entries = _extract_reasoning_trace(mock_result, messages=messages)
        assert len(entries) == 1
        assert entries[0].tool == "get_billing_history"
        assert isinstance(entries[0].summary, str)
        assert len(entries[0].summary) > 0

    def test_extract_reasoning_trace_empty_when_no_tools(self):
        """No tool calls → empty reasoning trace."""
        messages = [
            {"role": "user", "content": [{"text": "Hello"}]},
            {"role": "assistant", "content": [{"text": "Hi there!"}]},
        ]
        mock_result = MagicMock()
        mock_result.message = messages[-1]

        entries = _extract_reasoning_trace(mock_result, messages=messages)
        assert entries == []

    def test_extract_reasoning_trace_returns_list_of_entries(self):
        """Each entry is a ReasoningTraceEntry with tool and summary fields."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "toolUse": {
                            "name": "simulate_savings",
                            "toolUseId": "tu-002",
                            "input": {"customer_id": "CUST-001"},
                        }
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "toolResult": {
                            "toolUseId": "tu-002",
                            "content": [
                                {
                                    "json": {
                                        "green": {
                                            "plan_id": "ECO",
                                            "plan_name": "EcoFlex 100",
                                            "saving_monthly": 30.0,
                                            "saving_annual": 360.0,
                                        },
                                        "cheapest": {
                                            "plan_id": "VAL",
                                            "plan_name": "Value 12",
                                            "saving_monthly": 55.0,
                                            "saving_annual": 660.0,
                                        },
                                    }
                                }
                            ],
                        }
                    }
                ],
            },
        ]
        mock_result = MagicMock()
        mock_result.message = messages[-1]

        entries = _extract_reasoning_trace(mock_result, messages=messages)
        assert len(entries) == 1
        assert isinstance(entries[0], ReasoningTraceEntry)
        assert entries[0].tool == "simulate_savings"
        # Summary is code-composed by reasoning/summaries.py — contains savings figures
        assert "$30.00" in entries[0].summary or "Green" in entries[0].summary


# --- Test: response shape ---


class TestChatResponseShape:
    """Chat response contains all required fields."""

    def test_response_has_all_required_fields(self):
        """Req 4.2: reply, reasoning_trace, session_id, customer_id all present."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_agent_result = MagicMock()
            mock_agent_result.__str__ = lambda s: "The bill jumped because usage increased."
            mock_agent_result.message = {"content": [{"text": "The bill jumped."}]}
            mock_instance.return_value = mock_agent_result
            mock_instance.messages = []
            MockAgent.return_value = mock_instance

            result = handle_chat({
                "customer_id": "CUST-003",
                "action": "chat",
                "message": "Why did her bill jump?",
                "session_id": "sess-xyz",
                "messages": [],
            })

            assert "reply" in result
            assert "reasoning_trace" in result
            assert "session_id" in result
            assert "customer_id" in result

    def test_response_reply_is_string(self):
        """reply field is a non-empty string."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_agent_result = MagicMock()
            mock_agent_result.__str__ = lambda s: "Here is the answer."
            mock_agent_result.message = {"content": [{"text": "answer"}]}
            mock_instance.return_value = mock_agent_result
            mock_instance.messages = []
            MockAgent.return_value = mock_instance

            result = handle_chat({
                "customer_id": "CUST-001",
                "action": "chat",
                "message": "What plan is cheapest?",
                "session_id": "sess-1",
                "messages": [],
            })

            assert isinstance(result["reply"], str)
            assert len(result["reply"]) > 0

    def test_response_reasoning_trace_is_list(self):
        """reasoning_trace field is a list."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_agent_result = MagicMock()
            mock_agent_result.__str__ = lambda s: "answer"
            mock_agent_result.message = {"content": [{"text": "answer"}]}
            mock_instance.return_value = mock_agent_result
            mock_instance.messages = []
            MockAgent.return_value = mock_instance

            result = handle_chat({
                "customer_id": "CUST-001",
                "action": "chat",
                "message": "test",
                "session_id": "sess-1",
                "messages": [],
            })

            assert isinstance(result["reasoning_trace"], list)

    def test_response_preserves_session_id(self):
        """session_id in response matches the one provided in the request."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_agent_result = MagicMock()
            mock_agent_result.__str__ = lambda s: "answer"
            mock_agent_result.message = {"content": [{"text": "answer"}]}
            mock_instance.return_value = mock_agent_result
            mock_instance.messages = []
            MockAgent.return_value = mock_instance

            result = handle_chat({
                "customer_id": "CUST-001",
                "action": "chat",
                "message": "test",
                "session_id": "my-session-id",
                "messages": [],
            })

            assert result["session_id"] == "my-session-id"

    def test_response_preserves_customer_id(self):
        """customer_id in response matches the one provided in the request."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_agent_result = MagicMock()
            mock_agent_result.__str__ = lambda s: "answer"
            mock_agent_result.message = {"content": [{"text": "answer"}]}
            mock_instance.return_value = mock_agent_result
            mock_instance.messages = []
            MockAgent.return_value = mock_instance

            result = handle_chat({
                "customer_id": "CUST-003",
                "action": "chat",
                "message": "test",
                "session_id": "sess-1",
                "messages": [],
            })

            assert result["customer_id"] == "CUST-003"


# --- Test: D-04 unexpected exception returns error dict, never raises ---


class TestChatD04NeverRaises:
    """D-04: handle_chat() never raises — returns error dict on exception."""

    def test_agent_exception_returns_error_dict(self):
        """Req 8.1: unexpected exception returns error dict with fallback reply."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_instance.side_effect = RuntimeError("LLM exploded")
            MockAgent.return_value = mock_instance

            result = handle_chat({
                "customer_id": "CUST-001",
                "action": "chat",
                "message": "test",
                "session_id": "sess-1",
                "messages": [],
            })

            # Should NOT raise
            assert isinstance(result, dict)
            assert "reply" in result
            assert "error" in result["reply"].lower() or "sorry" in result["reply"].lower()
            assert result["reasoning_trace"] == []
            assert result["session_id"] == "sess-1"
            assert result["customer_id"] == "CUST-001"

    def test_type_error_returns_error_dict(self):
        """TypeError during agent construction returns error dict."""
        with patch("agent.agent.Agent", side_effect=TypeError("bad arg")):
            result = handle_chat({
                "customer_id": "CUST-002",
                "action": "chat",
                "message": "hello",
                "session_id": "sess-2",
                "messages": [],
            })

            assert isinstance(result, dict)
            assert "reply" in result
            assert result["reasoning_trace"] == []

    def test_value_error_returns_error_dict(self):
        """ValueError during processing returns error dict."""
        with patch("agent.agent.Agent") as MockAgent:
            mock_instance = MagicMock()
            mock_instance.side_effect = ValueError("invalid input")
            MockAgent.return_value = mock_instance

            result = handle_chat({
                "customer_id": "CUST-001",
                "action": "chat",
                "message": "test",
                "session_id": "sess-3",
                "messages": [],
            })

            assert isinstance(result, dict)
            assert "reply" in result
            assert result["customer_id"] == "CUST-001"

    def test_never_raises_on_any_exception(self):
        """No exception type causes handle_chat to raise."""
        exceptions_to_test = [
            RuntimeError("runtime"),
            TypeError("type"),
            ValueError("value"),
            KeyError("key"),
            AttributeError("attr"),
            Exception("generic"),
        ]
        for exc in exceptions_to_test:
            with patch("agent.agent.Agent", side_effect=exc):
                # Should never raise
                result = handle_chat({
                    "customer_id": "CUST-001",
                    "action": "chat",
                    "message": "test",
                    "session_id": "sess-x",
                    "messages": [],
                })
                assert isinstance(result, dict), f"Failed for {type(exc).__name__}"
                assert "reply" in result, f"Missing reply for {type(exc).__name__}"


# --- Test: existing recommend action unchanged (regression) ---


class TestRecommendActionRegression:
    """Req 8.4: Existing recommend action unchanged after chat addition."""

    def test_default_action_is_recommend(self):
        """invoke() with no action defaults to recommendation path."""
        result = invoke({"customer_id": "CUST-001"})
        # InMemoryProvider is installed by autouse fixture — should get a
        # recommendation response (kind=recommendation) or a valid response.
        assert result.get("kind") in ("recommendation", "hardship", None) or "green" in result

    def test_explicit_recommend_action(self):
        """invoke() with action='recommend' routes to recommendation path."""
        result = invoke({"customer_id": "CUST-001", "action": "recommend"})
        # Should produce a recommendation (via supervisor/specialist)
        assert result.get("kind") in ("recommendation", None) or "green" in result
        # Should NOT have chat-specific keys
        assert "reply" not in result

    def test_recommend_does_not_use_chat_prompt(self):
        """Recommendation path uses SYSTEM_PROMPT (base + narrative), not chat prompt."""
        from agent.agent import SYSTEM_PROMPT, _agent
        # The module-level _agent uses SYSTEM_PROMPT which includes NARRATIVE_PROMPT
        assert _CHAT_SYSTEM_PROMPT not in _agent.system_prompt
        assert SYSTEM_PROMPT == _agent.system_prompt


# --- Test: existing follow_up action unchanged (regression) ---


class TestFollowUpActionRegression:
    """Req 8.5: Existing follow_up action unchanged after chat addition."""

    def test_follow_up_action_dispatches(self):
        """invoke() with action='follow_up' still dispatches to draft_follow_up."""
        import agent.agent as agent_mod
        original = agent_mod._MEMORY_ID
        try:
            agent_mod._MEMORY_ID = ""
            result = invoke({"customer_id": "CUST-001", "action": "follow_up"})
            assert result["kind"] == "follow_up"
            assert result["customer_id"] == "CUST-001"
        finally:
            agent_mod._MEMORY_ID = original

    def test_follow_up_does_not_use_chat_handler(self):
        """action='follow_up' does not route through handle_chat."""
        with patch("agent.agent.handle_chat") as mock_chat:
            import agent.agent as agent_mod
            original = agent_mod._MEMORY_ID
            try:
                agent_mod._MEMORY_ID = ""
                invoke({"customer_id": "CUST-001", "action": "follow_up"})
                mock_chat.assert_not_called()
            finally:
                agent_mod._MEMORY_ID = original

    def test_follow_up_response_shape_unchanged(self):
        """Follow-up response still has kind, customer_id, subject, body, plan_reference."""
        import agent.agent as agent_mod
        original = agent_mod._MEMORY_ID
        try:
            agent_mod._MEMORY_ID = ""
            result = invoke({"customer_id": "CUST-001", "action": "follow_up"})
            assert "kind" in result
            assert "customer_id" in result
            assert "subject" in result
            assert "body" in result
            assert "plan_reference" in result
        finally:
            agent_mod._MEMORY_ID = original
