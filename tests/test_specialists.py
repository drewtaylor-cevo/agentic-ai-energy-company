"""Unit tests for specialist agents (HardshipSpecialist, TariffSpecialist).

Task 2: HardshipSpecialist tests
  - Returns HardshipResponse shape (kind, customer_id, reason, routing_target, call_script)
  - Has no tariff tool references (no simulate_savings, detect_bill_shock, get_billing_history)
  - Satisfies AgentRole Protocol via isinstance check
  - Attaches _narrative_source with hardship markers

Task 3 will add TariffSpecialist tests to this file.
"""
import inspect

from agent.specialists.hardship import HardshipSpecialist
from agent.roles import AgentRole


# --- HardshipSpecialist: AgentRole Protocol conformance (Req 5.3) ---


class TestHardshipSpecialistProtocol:
    """HardshipSpecialist satisfies AgentRole Protocol."""

    def test_satisfies_agent_role_protocol(self):
        """isinstance(HardshipSpecialist(), AgentRole) is True."""
        specialist = HardshipSpecialist()
        assert isinstance(specialist, AgentRole)

    def test_has_handle_method(self):
        """HardshipSpecialist has a handle() method."""
        specialist = HardshipSpecialist()
        assert hasattr(specialist, "handle")
        assert callable(specialist.handle)


# --- HardshipSpecialist: response shape (Req 2.3) ---


class TestHardshipSpecialistResponse:
    """HardshipSpecialist.handle() returns a valid HardshipResponse shape."""

    def test_returns_hardship_kind(self):
        """Response has kind: 'hardship'."""
        specialist = HardshipSpecialist()
        response = specialist.handle({"customer_id": "CUST-006"})
        assert response["kind"] == "hardship"

    def test_returns_customer_id(self):
        """Response includes the customer_id from the payload."""
        specialist = HardshipSpecialist()
        response = specialist.handle({"customer_id": "CUST-006"})
        assert response["customer_id"] == "CUST-006"

    def test_returns_reason(self):
        """Response includes a reason string."""
        specialist = HardshipSpecialist()
        response = specialist.handle({"customer_id": "CUST-006"})
        assert isinstance(response["reason"], str)
        assert len(response["reason"]) > 0

    def test_returns_routing_target(self):
        """Response includes routing_target: 'hardship_team'."""
        specialist = HardshipSpecialist()
        response = specialist.handle({"customer_id": "CUST-006"})
        assert response["routing_target"] == "hardship_team"

    def test_returns_call_script(self):
        """Response includes a call_script string."""
        specialist = HardshipSpecialist()
        response = specialist.handle({"customer_id": "CUST-006"})
        assert isinstance(response["call_script"], str)
        assert len(response["call_script"]) > 0

    def test_no_green_or_cheapest_tracks(self):
        """Hardship response has no green or cheapest tracks."""
        specialist = HardshipSpecialist()
        response = specialist.handle({"customer_id": "CUST-006"})
        assert "green" not in response
        assert "cheapest" not in response

    def test_attaches_narrative_source(self):
        """Response includes _narrative_source with hardship markers."""
        specialist = HardshipSpecialist()
        response = specialist.handle({"customer_id": "CUST-006"})
        assert "_narrative_source" in response
        ns = response["_narrative_source"]
        assert "hardship" in ns
        assert ns["hardship"]["reason"] == "fallback"
        assert ns["hardship"]["call_script"] == "fallback"


# --- HardshipSpecialist: no tariff tools (Req 2.4) ---


class TestHardshipSpecialistNoTariffTools:
    """HardshipSpecialist source code contains no tariff tool references."""

    def test_no_simulate_savings_reference(self):
        """Source code does not reference simulate_savings."""
        source = inspect.getsource(HardshipSpecialist)
        assert "simulate_savings" not in source

    def test_no_detect_bill_shock_reference(self):
        """Source code does not reference detect_bill_shock."""
        source = inspect.getsource(HardshipSpecialist)
        assert "detect_bill_shock" not in source

    def test_no_get_billing_history_reference(self):
        """Source code does not reference get_billing_history."""
        source = inspect.getsource(HardshipSpecialist)
        assert "get_billing_history" not in source


# --- TariffSpecialist tests (Task 3) ---

from unittest.mock import MagicMock, patch, PropertyMock
from agent.specialists.tariff import TariffSpecialist
from agent.hooks.four_tool_cap import FourToolCapHook


# --- TariffSpecialist: AgentRole Protocol conformance (Req 5.3) ---


class TestTariffSpecialistProtocol:
    """TariffSpecialist satisfies AgentRole Protocol."""

    def test_satisfies_agent_role_protocol(self):
        """isinstance(TariffSpecialist(...), AgentRole) is True."""
        mock_agent = MagicMock()
        mock_cap = MagicMock(spec=FourToolCapHook)
        specialist = TariffSpecialist(mock_agent, mock_cap)
        assert isinstance(specialist, AgentRole)

    def test_has_handle_method(self):
        """TariffSpecialist has a handle() method."""
        mock_agent = MagicMock()
        mock_cap = MagicMock(spec=FourToolCapHook)
        specialist = TariffSpecialist(mock_agent, mock_cap)
        assert hasattr(specialist, "handle")
        assert callable(specialist.handle)


# --- TariffSpecialist: reuses module-level instances (Req 6.4) ---


class TestTariffSpecialistReusesInstances:
    """TariffSpecialist stores the agent and four_tool_cap references passed to it."""

    def test_stores_agent_reference(self):
        """Constructor stores the agent instance — no new Agent created."""
        mock_agent = MagicMock()
        mock_cap = MagicMock(spec=FourToolCapHook)
        specialist = TariffSpecialist(mock_agent, mock_cap)
        assert specialist._agent is mock_agent

    def test_stores_four_tool_cap_reference(self):
        """Constructor stores the FourToolCapHook instance."""
        mock_agent = MagicMock()
        mock_cap = MagicMock(spec=FourToolCapHook)
        specialist = TariffSpecialist(mock_agent, mock_cap)
        assert specialist._four_tool_cap is mock_cap


# --- TariffSpecialist: handle() attaches _narrative_source and reasoning_trace (Req 3.5) ---


class TestTariffSpecialistHandle:
    """TariffSpecialist.handle() attaches _narrative_source and reasoning_trace."""

    def _make_mock_agent_result(self):
        """Create a mock agent result with structured_output returning a valid RecommendationResponse."""
        from agent.agent import RecommendationResponse, TrackInfo

        track_green = TrackInfo(
            plan_id="ECO",
            plan_name="EcoFlex 100",
            saving_monthly=30.00,
            saving_annual=360.00,
            usage_narrative="Strong cool-season usage with a family-sized load across the year.",
            call_script="Ask about EcoFlex — it suits a strong winter-heating profile like yours.",
        )
        track_cheapest = TrackInfo(
            plan_id="VAL",
            plan_name="Value 12",
            saving_monthly=55.00,
            saving_annual=660.00,
            usage_narrative="Consistently high household consumption with cool-season peaks.",
            call_script="Bring up Value Twelve — a budget-first pick for a high-usage home.",
        )
        recommendation = RecommendationResponse(
            green=track_green,
            cheapest=track_cheapest,
            reasoning_trace=[],
        )

        agent_result = MagicMock()
        agent_result.stop_reason = "end_turn"
        agent_result.structured_output = recommendation
        agent_result.message = {"content": []}
        return agent_result

    def test_attaches_narrative_source_on_happy_path(self):
        """Happy path: response includes _narrative_source with model markers."""
        mock_agent = MagicMock()
        mock_cap = MagicMock(spec=FourToolCapHook)
        mock_agent.messages = []

        agent_result = self._make_mock_agent_result()
        mock_agent.return_value = agent_result

        specialist = TariffSpecialist(mock_agent, mock_cap)
        response = specialist.handle({"customer_id": "CUST-001"})

        assert "_narrative_source" in response
        ns = response["_narrative_source"]
        assert "green" in ns
        assert "cheapest" in ns
        assert ns["green"]["usage_narrative"] == "model"
        assert ns["cheapest"]["usage_narrative"] == "model"

    def test_attaches_reasoning_trace_on_happy_path(self):
        """Happy path: response includes reasoning_trace list."""
        mock_agent = MagicMock()
        mock_cap = MagicMock(spec=FourToolCapHook)
        mock_agent.messages = []

        agent_result = self._make_mock_agent_result()
        mock_agent.return_value = agent_result

        specialist = TariffSpecialist(mock_agent, mock_cap)
        response = specialist.handle({"customer_id": "CUST-001"})

        assert "reasoning_trace" in response
        assert isinstance(response["reasoning_trace"], list)

    def test_resets_four_tool_cap_before_agent_call(self):
        """handle() resets the FourToolCapHook before calling the agent."""
        mock_agent = MagicMock()
        mock_cap = MagicMock(spec=FourToolCapHook)
        mock_agent.messages = []

        agent_result = self._make_mock_agent_result()
        mock_agent.return_value = agent_result

        specialist = TariffSpecialist(mock_agent, mock_cap)
        specialist.handle({"customer_id": "CUST-001"})

        mock_cap.reset.assert_called_once()

    def test_fallback_path_attaches_narrative_source(self):
        """General exception fallback: response still includes _narrative_source."""
        mock_agent = MagicMock()
        mock_cap = MagicMock(spec=FourToolCapHook)
        mock_agent.messages = []

        # Agent call raises a generic exception
        mock_agent.side_effect = RuntimeError("agent failed")

        specialist = TariffSpecialist(mock_agent, mock_cap)

        # Mock _fetch_deterministic_savings to return valid savings
        with patch("agent.specialists.tariff._fetch_deterministic_savings") as mock_fetch:
            mock_fetch.return_value = {
                "green": {
                    "plan_id": "ECO",
                    "plan_name": "EcoFlex 100",
                    "saving_monthly": 30.00,
                    "saving_annual": 360.00,
                },
                "cheapest": {
                    "plan_id": "VAL",
                    "plan_name": "Value 12",
                    "saving_monthly": 55.00,
                    "saving_annual": 660.00,
                },
            }
            response = specialist.handle({"customer_id": "CUST-001"})

        assert "_narrative_source" in response
        assert "reasoning_trace" in response
