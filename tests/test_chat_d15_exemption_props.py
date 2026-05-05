# Feature: conversational-chat-layer, Property 5: Reply D-15 exemption
"""Property-based tests for reply D-15 exemption.

**Validates: Requirements 2.6**

For any chat response where the `reply` field contains digits, currency symbols ($),
percentages (%), or date strings, the response SHALL still be valid — the reply field
is NOT subject to D-15 narrative validators.

The D-15 validators in `agent/narrative/validators.py` reject digits, currency,
percentages in `usage_narrative` and `call_script` fields. The chat `reply` field
is exempt from these validators.
"""

import json
import re
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from api_lambda.chat_handler import chat_handler
from agent.narrative.banned_terms import NUMERIC_REGEX, BANNED_REGEX


# --- Strategies ---

# Valid customer IDs for all tests.
_valid_customer_id_strategy = st.from_regex(r"CUST-\d{3,6}", fullmatch=True)

# Valid messages for all tests.
_valid_message_strategy = st.text(min_size=1, max_size=100).filter(
    lambda s: s.strip() and len(s) <= 2000
)


# Strategy: generate reply strings containing digits.
_reply_with_digits = st.one_of(
    st.from_regex(r"[A-Za-z ]{1,20}\d+[A-Za-z ]{0,20}", fullmatch=True),
    st.builds(
        lambda prefix, num, suffix: f"{prefix}{num}{suffix}",
        prefix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=20),
        num=st.integers(min_value=0, max_value=999999),
        suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=20),
    ),
)

# Strategy: generate reply strings containing currency symbols.
_reply_with_currency = st.one_of(
    st.builds(
        lambda prefix, symbol, amount, suffix: f"{prefix}{symbol}{amount}{suffix}",
        prefix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=20),
        symbol=st.sampled_from(["$", "£", "€"]),
        amount=st.from_regex(r"\d{1,6}\.\d{2}", fullmatch=True),
        suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=20),
    ),
)

# Strategy: generate reply strings containing percentages.
_reply_with_percentages = st.builds(
    lambda prefix, num, suffix: f"{prefix}{num}%{suffix}",
    prefix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=20),
    num=st.integers(min_value=1, max_value=100),
    suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=20),
)

# Strategy: generate reply strings containing date strings.
_reply_with_dates = st.one_of(
    # ISO format: 2025-02-15
    st.builds(
        lambda prefix, y, m, d, suffix: f"{prefix}{y}-{m:02d}-{d:02d}{suffix}",
        prefix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=20),
        y=st.integers(min_value=2020, max_value=2030),
        m=st.integers(min_value=1, max_value=12),
        d=st.integers(min_value=1, max_value=28),
        suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=20),
    ),
    # Slash format: 15/02/2025
    st.builds(
        lambda prefix, d, m, y, suffix: f"{prefix}{d:02d}/{m:02d}/{y}{suffix}",
        prefix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=20),
        d=st.integers(min_value=1, max_value=28),
        m=st.integers(min_value=1, max_value=12),
        y=st.integers(min_value=2020, max_value=2030),
        suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=20),
    ),
    # Month name format: February 2025
    st.builds(
        lambda prefix, month, y, suffix: f"{prefix}{month} {y}{suffix}",
        prefix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=20),
        month=st.sampled_from([
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]),
        y=st.integers(min_value=2020, max_value=2030),
        suffix=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=20),
    ),
)

# Combined strategy: replies that would FAIL D-15 validators.
_d15_violating_reply_strategy = st.one_of(
    _reply_with_digits,
    _reply_with_currency,
    _reply_with_percentages,
    _reply_with_dates,
)


# --- Helpers ---

def _make_event(customer_id: str, message: str) -> dict:
    """Build a minimal Lambda proxy event for the chat handler."""
    return {
        "rawPath": f"/chat/{customer_id}",
        "pathParameters": {"customer_id": customer_id},
        "body": json.dumps({"message": message}),
        "headers": {"content-type": "application/json"},
    }


def _make_mock_session(customer_id: str) -> MagicMock:
    """Create a mock session object for patching session_store."""
    mock_session = MagicMock()
    mock_session.session_id = "test-session-id"
    mock_session.customer_id = customer_id
    mock_session.messages = []
    return mock_session


def _make_mock_agentcore_response(reply: str, reasoning_trace: list[dict]) -> MagicMock:
    """Create a mock AgentCore response with the given reply and trace."""
    response_body = json.dumps({
        "reply": reply,
        "reasoning_trace": reasoning_trace,
    }).encode()

    mock_response_stream = MagicMock()
    mock_response_stream.read.return_value = response_body

    return {"response": mock_response_stream}


# --- Property Tests ---

@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
    reply=_d15_violating_reply_strategy,
)
def test_reply_with_d15_violating_content_returns_200(
    customer_id: str,
    message: str,
    reply: str,
) -> None:
    """Chat replies containing digits, currency, percentages, or dates are NOT rejected.

    **Validates: Requirements 2.6**

    The D-15 validators (NUMERIC_REGEX, BANNED_REGEX) apply to `usage_narrative`
    and `call_script` fields only. The chat `reply` field is exempt — it is
    free-text conversational output that legitimately contains numeric data
    from tool results.

    This test generates reply strings that would FAIL D-15 validators and
    verifies the chat handler still returns HTTP 200.
    """
    # Confirm the generated reply actually contains D-15-violating content.
    assume(NUMERIC_REGEX.search(reply) is not None)

    event = _make_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        # Configure session store.
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False

        # Configure AgentCore to return a reply with D-15-violating content.
        mock_client.invoke_agent_runtime.return_value = _make_mock_agentcore_response(
            reply,
            [{"tool": "get_billing_history", "summary": "12 months retrieved"}],
        )

        result = chat_handler(event, None)

    # The handler MUST return 200 — the reply is NOT subject to D-15 validators.
    assert result["statusCode"] == 200, (
        f"Expected 200 for reply with D-15-violating content, got {result['statusCode']}. "
        f"Reply: '{reply[:80]}...'"
    )

    # Verify the reply is passed through unchanged.
    body = json.loads(result["body"])
    assert body["reply"] == reply, (
        f"Reply was modified or rejected. Expected: '{reply[:80]}...', "
        f"Got: '{body['reply'][:80]}...'"
    )


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
    reply=_reply_with_currency,
)
def test_reply_with_currency_symbols_not_rejected(
    customer_id: str,
    message: str,
    reply: str,
) -> None:
    """Chat replies containing currency symbols ($, £, €) are valid and not filtered.

    **Validates: Requirements 2.6**

    D-15 NUMERIC_REGEX rejects any string containing $ £ € in narrative fields.
    The chat reply field is exempt — currency values from tools are expected.
    """
    # Confirm the reply contains currency symbols.
    assume(any(c in reply for c in "$£€"))

    event = _make_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False

        mock_client.invoke_agent_runtime.return_value = _make_mock_agentcore_response(
            reply,
            [{"tool": "simulate_savings", "summary": "Savings calculated"}],
        )

        result = chat_handler(event, None)

    assert result["statusCode"] == 200, (
        f"Expected 200 for reply with currency symbols, got {result['statusCode']}. "
        f"Reply: '{reply[:80]}...'"
    )

    body = json.loads(result["body"])
    assert body["reply"] == reply


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
    reply=_reply_with_percentages,
)
def test_reply_with_percentages_not_rejected(
    customer_id: str,
    message: str,
    reply: str,
) -> None:
    """Chat replies containing percentage values are valid and not filtered.

    **Validates: Requirements 2.6**

    D-15 NUMERIC_REGEX rejects any string containing % in narrative fields.
    The chat reply field is exempt — percentage values from tools are expected.
    """
    # Confirm the reply contains a percentage.
    assume("%" in reply)

    event = _make_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False

        mock_client.invoke_agent_runtime.return_value = _make_mock_agentcore_response(
            reply,
            [{"tool": "detect_bill_shock", "summary": "Bill shock detected"}],
        )

        result = chat_handler(event, None)

    assert result["statusCode"] == 200, (
        f"Expected 200 for reply with percentages, got {result['statusCode']}. "
        f"Reply: '{reply[:80]}...'"
    )

    body = json.loads(result["body"])
    assert body["reply"] == reply


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
    reply=_reply_with_dates,
)
def test_reply_with_date_strings_not_rejected(
    customer_id: str,
    message: str,
    reply: str,
) -> None:
    """Chat replies containing date strings are valid and not filtered.

    **Validates: Requirements 2.6**

    D-15 NUMERIC_REGEX rejects any string containing digits in narrative fields.
    Date strings contain digits (e.g., 2025-02-15, 15/02/2025). The chat reply
    field is exempt — dates from tool results are expected in conversational output.
    """
    # Confirm the reply contains digits (from the date).
    assume(re.search(r"\d", reply) is not None)

    event = _make_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        mock_store.get_or_create.return_value = _make_mock_session(customer_id)
        mock_store.check_rate_limit.return_value = False

        mock_client.invoke_agent_runtime.return_value = _make_mock_agentcore_response(
            reply,
            [{"tool": "get_billing_history", "summary": "History retrieved"}],
        )

        result = chat_handler(event, None)

    assert result["statusCode"] == 200, (
        f"Expected 200 for reply with date strings, got {result['statusCode']}. "
        f"Reply: '{reply[:80]}...'"
    )

    body = json.loads(result["body"])
    assert body["reply"] == reply
