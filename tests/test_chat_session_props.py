# Feature: conversational-chat-layer, Property 3: Session ID uniqueness
"""Property-based tests for ChatSessionStore session ID uniqueness.

**Validates: Requirements 1.4**

For any N chat invocations without a provided session_id, all N generated
session IDs SHALL be distinct (uuid4 uniqueness guarantee).
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from api_lambda.chat_session import ChatSessionStore, _sessions


@settings(max_examples=100)
@given(
    n=st.integers(min_value=2, max_value=50),
    customer_id=st.from_regex(r"CUST-\d{3,6}", fullmatch=True),
)
def test_session_id_uniqueness(n: int, customer_id: str) -> None:
    """For any N invocations without a session_id, all generated IDs are distinct.

    **Validates: Requirements 1.4**
    """
    # Clear module-level state to avoid leakage between test iterations.
    _sessions.clear()

    store = ChatSessionStore()
    session_ids: list[str] = []

    for _ in range(n):
        session = store.get_or_create(session_id=None, customer_id=customer_id)
        session_ids.append(session.session_id)

    # All generated session IDs must be unique.
    assert len(set(session_ids)) == len(session_ids), (
        f"Duplicate session IDs found among {n} invocations: "
        f"{[sid for sid in session_ids if session_ids.count(sid) > 1]}"
    )

    # Cleanup.
    _sessions.clear()

# Feature: conversational-chat-layer, Property 8: Session isolation (SC-3)


import pytest


@settings(max_examples=100)
@given(
    customer_a=st.from_regex(r"CUST-\d{3,6}", fullmatch=True),
    customer_b=st.from_regex(r"CUST-\d{3,6}", fullmatch=True),
)
def test_session_isolation(customer_a: str, customer_b: str) -> None:
    """For any session created for customer_id A, using it with customer_id B raises ValueError.

    **Validates: Requirements 5.1, 5.2, 8.3**

    For any session created for customer_id A, attempting to use that session_id
    with a different customer_id B (where A ≠ B) SHALL be rejected with ValueError
    (HTTP 400 in the handler).
    """
    # Ensure distinct customer IDs.
    assume(customer_a != customer_b)

    # Clear module-level state to avoid leakage between test iterations.
    _sessions.clear()

    store = ChatSessionStore()

    # Create a session for customer A.
    session = store.get_or_create(session_id=None, customer_id=customer_a)
    created_session_id = session.session_id

    # Attempting to use that session_id with customer B must raise ValueError.
    with pytest.raises(ValueError, match="Session belongs to a different customer"):
        store.get_or_create(session_id=created_session_id, customer_id=customer_b)

    # Cleanup.
    _sessions.clear()

# Feature: conversational-chat-layer, Property 9: Session turn cap


@settings(max_examples=100)
@given(
    customer_id=st.from_regex(r"CUST-\d{3,6}", fullmatch=True),
    extra_turns=st.integers(min_value=0, max_value=10),
)
def test_session_turn_cap(customer_id: str, extra_turns: int) -> None:
    """After 20 completed turns, the next request receives a new session_id.

    **Validates: Requirements 5.5**

    For any chat session, after 20 completed turns (user message + assistant
    reply pairs), the next request using that session_id SHALL receive a new
    session_id in the response (session closed, new one created).
    """
    # Clear module-level state to avoid leakage between test iterations.
    _sessions.clear()

    store = ChatSessionStore()

    # Create a session for the customer.
    session = store.get_or_create(session_id=None, customer_id=customer_id)
    original_session_id = session.session_id

    # Record exactly 20 turns (the maximum allowed).
    for i in range(20):
        store.record_turn(
            original_session_id,
            user_msg=f"user message {i}",
            assistant_msg=f"assistant reply {i}",
        )

    # Verify the session now has turn_count == 20.
    assert _sessions[original_session_id].turn_count == 20

    # The next get_or_create with the same session_id must return a NEW session.
    new_session = store.get_or_create(
        session_id=original_session_id, customer_id=customer_id
    )
    assert new_session.session_id != original_session_id, (
        f"Session should have been closed after 20 turns, but same session_id "
        f"'{original_session_id}' was returned."
    )
    # The new session must belong to the same customer.
    assert new_session.customer_id == customer_id
    # The new session must start with 0 turns.
    assert new_session.turn_count == 0
    # The old session must no longer exist in the store.
    assert original_session_id not in _sessions

    # Additionally, if we record more turns on the new session (up to extra_turns),
    # it should remain valid as long as turn_count < 20.
    for i in range(extra_turns):
        store.record_turn(
            new_session.session_id,
            user_msg=f"new user message {i}",
            assistant_msg=f"new assistant reply {i}",
        )

    if extra_turns < 20:
        # Session should still be reusable.
        reused = store.get_or_create(
            session_id=new_session.session_id, customer_id=customer_id
        )
        assert reused.session_id == new_session.session_id

    # Cleanup.
    _sessions.clear()

# Feature: conversational-chat-layer, Property 10: Rate limiting enforcement

import time
from unittest.mock import patch


@settings(max_examples=100)
@given(
    customer_id=st.from_regex(r"CUST-\d{3,6}", fullmatch=True),
    extra_messages=st.integers(min_value=1, max_value=10),
)
def test_rate_limiting_enforcement(customer_id: str, extra_messages: int) -> None:
    """Sending more than 10 messages within 60s results in rate limit exceeded.

    **Validates: Requirements 10.4**

    For any chat session, sending more than 10 messages within a 60-second
    window SHALL result in the rate limit being exceeded (check_rate_limit
    returns True) for subsequent messages until the window expires.
    """
    # Clear module-level state to avoid leakage between test iterations.
    _sessions.clear()

    store = ChatSessionStore()

    # Create a session for the customer.
    session = store.get_or_create(session_id=None, customer_id=customer_id)
    session_id = session.session_id

    # Send exactly 10 messages — all should be allowed (return False).
    for i in range(10):
        result = store.check_rate_limit(session_id)
        assert result is False, (
            f"Message {i + 1} of 10 should be allowed, but rate limit returned True"
        )

    # The 11th message (and any additional) should be rate-limited (return True).
    for i in range(extra_messages):
        result = store.check_rate_limit(session_id)
        assert result is True, (
            f"Message {11 + i} should be rate-limited, but check_rate_limit returned False"
        )

    # Cleanup.
    _sessions.clear()


@settings(max_examples=100)
@given(
    customer_id=st.from_regex(r"CUST-\d{3,6}", fullmatch=True),
)
def test_rate_limit_window_expiry(customer_id: str) -> None:
    """Rate limit resets after the 60-second window expires.

    **Validates: Requirements 10.4**

    For any chat session that has exceeded the rate limit, once the 60-second
    window expires, subsequent messages SHALL be allowed again.
    """
    # Clear module-level state to avoid leakage between test iterations.
    _sessions.clear()

    store = ChatSessionStore()

    # Create a session for the customer.
    session = store.get_or_create(session_id=None, customer_id=customer_id)
    session_id = session.session_id

    # Use a fixed base time for deterministic testing.
    base_time = 1000000.0

    # Send 10 messages within the window — all allowed.
    with patch("api_lambda.chat_session.time.time", return_value=base_time):
        for i in range(10):
            result = store.check_rate_limit(session_id)
            assert result is False, (
                f"Message {i + 1} should be allowed within the window"
            )

    # 11th message at same time — should be rate-limited.
    with patch("api_lambda.chat_session.time.time", return_value=base_time + 30):
        result = store.check_rate_limit(session_id)
        assert result is True, "Message 11 within window should be rate-limited"

    # After 61 seconds from the original messages, the window has expired.
    # All old timestamps are now outside the window, so messages should be allowed.
    with patch("api_lambda.chat_session.time.time", return_value=base_time + 61):
        result = store.check_rate_limit(session_id)
        assert result is False, (
            "After window expiry, messages should be allowed again"
        )

    # Cleanup.
    _sessions.clear()
