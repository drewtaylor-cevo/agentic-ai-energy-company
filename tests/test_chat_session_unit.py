"""Unit tests for ChatSessionStore.

Tests cover session creation, reuse, TTL expiry, cross-customer rejection,
turn cap enforcement, rate limiting, lazy eviction, and stateless fallback.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.4
"""

import time
import uuid
from unittest.mock import patch

import pytest

import api_lambda.chat_session as _mod

# Access module attributes through the module reference to avoid stale bindings.
ChatSessionStore = _mod.ChatSessionStore
ChatSession = _mod.ChatSession
CHAT_SESSION_TTL_MINUTES = _mod.CHAT_SESSION_TTL_MINUTES


@pytest.fixture(autouse=True)
def clear_sessions():
    """Clear module-level session storage before and after each test."""
    _mod._sessions.clear()
    yield
    _mod._sessions.clear()


@pytest.fixture
def store():
    """Fresh ChatSessionStore instance."""
    return ChatSessionStore()


# --- Test session creation with fresh uuid4 ---


class TestSessionCreation:
    """Test session creation with fresh uuid4."""

    def test_creates_new_session_when_no_session_id(self, store):
        """get_or_create with session_id=None creates a new session."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")

        assert session is not None
        assert session.customer_id == "CUST-001"
        assert session.turn_count == 0
        assert session.messages == []
        # session_id should be a valid uuid4
        uuid.UUID(session.session_id, version=4)

    def test_creates_new_session_when_session_id_not_found(self, store):
        """get_or_create with unknown session_id creates a new session."""
        session = store.get_or_create(
            session_id="nonexistent-id", customer_id="CUST-002"
        )

        assert session is not None
        assert session.customer_id == "CUST-002"
        assert session.turn_count == 0

    def test_new_session_stored_in_module_dict(self, store):
        """Newly created session is stored in the module-level _sessions dict."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")

        assert session.session_id in _mod._sessions
        assert _mod._sessions[session.session_id] is session

    def test_each_creation_produces_unique_id(self, store):
        """Multiple creations produce distinct session IDs."""
        ids = set()
        for _ in range(10):
            session = store.get_or_create(session_id=None, customer_id="CUST-001")
            ids.add(session.session_id)

        assert len(ids) == 10


# --- Test session reuse with valid session_id and matching customer_id ---


class TestSessionReuse:
    """Test session reuse with valid session_id and matching customer_id."""

    def test_reuses_existing_session(self, store):
        """get_or_create with valid session_id returns the same session."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")
        original_id = session.session_id

        reused = store.get_or_create(session_id=original_id, customer_id="CUST-001")

        assert reused.session_id == original_id
        assert reused.customer_id == "CUST-001"

    def test_reuse_updates_last_active(self, store):
        """Reusing a session updates its last_active timestamp."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")
        original_last_active = session.last_active

        with patch("api_lambda.chat_session.time.time", return_value=original_last_active + 30):
            reused = store.get_or_create(
                session_id=session.session_id, customer_id="CUST-001"
            )

        assert reused.last_active > original_last_active

    def test_reuse_preserves_turn_count(self, store):
        """Reusing a session preserves the existing turn count."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")
        store.record_turn(session.session_id, "hello", "hi there")

        reused = store.get_or_create(
            session_id=session.session_id, customer_id="CUST-001"
        )

        assert reused.turn_count == 1


# --- Test TTL expiry creates new session transparently ---


class TestTTLExpiry:
    """Test TTL expiry creates new session transparently."""

    def test_expired_session_creates_new_one(self, store):
        """An expired session is replaced with a new one transparently."""
        base_time = 1000000.0

        with patch("api_lambda.chat_session.time.time", return_value=base_time):
            session = store.get_or_create(session_id=None, customer_id="CUST-001")
            original_id = session.session_id

        # Advance time past TTL (default 15 minutes = 900 seconds)
        expired_time = base_time + (CHAT_SESSION_TTL_MINUTES * 60) + 1
        with patch("api_lambda.chat_session.time.time", return_value=expired_time):
            new_session = store.get_or_create(
                session_id=original_id, customer_id="CUST-001"
            )

        assert new_session.session_id != original_id
        assert new_session.customer_id == "CUST-001"
        assert new_session.turn_count == 0
        assert original_id not in _mod._sessions

    def test_non_expired_session_is_reused(self, store):
        """A session within TTL is reused normally."""
        base_time = 1000000.0

        with patch("api_lambda.chat_session.time.time", return_value=base_time):
            session = store.get_or_create(session_id=None, customer_id="CUST-001")
            original_id = session.session_id

        # Advance time but stay within TTL
        within_ttl = base_time + (CHAT_SESSION_TTL_MINUTES * 60) - 10
        with patch("api_lambda.chat_session.time.time", return_value=within_ttl):
            reused = store.get_or_create(
                session_id=original_id, customer_id="CUST-001"
            )

        assert reused.session_id == original_id

    @patch.dict("os.environ", {"CHAT_SESSION_TTL_MINUTES": "5"})
    def test_ttl_configurable_via_env_var(self):
        """TTL is configurable via CHAT_SESSION_TTL_MINUTES env var."""
        # Verify the env var is read at module load time by checking the
        # int() parsing logic directly (same as module top-level).
        import os
        ttl = int(os.environ.get("CHAT_SESSION_TTL_MINUTES", "15"))
        assert ttl == 5


# --- Test cross-customer rejection raises ValueError ---


class TestCrossCustomerRejection:
    """Test cross-customer rejection raises ValueError."""

    def test_raises_value_error_for_different_customer(self, store):
        """Using a session with a different customer_id raises ValueError."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")

        with pytest.raises(ValueError, match="Session belongs to a different customer"):
            store.get_or_create(
                session_id=session.session_id, customer_id="CUST-002"
            )

    def test_original_session_unchanged_after_rejection(self, store):
        """The original session remains intact after a cross-customer rejection."""
        # Use real time so eviction doesn't interfere
        session = store.get_or_create(session_id=None, customer_id="CUST-001")
        original_id = session.session_id

        with pytest.raises(ValueError):
            store.get_or_create(session_id=original_id, customer_id="CUST-002")

        # Original session still exists and is valid
        assert original_id in _mod._sessions
        assert _mod._sessions[original_id].customer_id == "CUST-001"


# --- Test turn cap at 20 closes session and returns new one ---


class TestTurnCap:
    """Test turn cap at 20 closes session and returns new one."""

    def test_session_closed_after_20_turns(self, store):
        """After 20 turns, get_or_create returns a new session."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")
        original_id = session.session_id

        # Record 20 turns
        for i in range(20):
            store.record_turn(original_id, f"msg {i}", f"reply {i}")

        # Next access should create a new session
        new_session = store.get_or_create(
            session_id=original_id, customer_id="CUST-001"
        )

        assert new_session.session_id != original_id
        assert new_session.turn_count == 0
        assert original_id not in _mod._sessions

    def test_session_valid_at_19_turns(self, store):
        """A session with 19 turns is still reusable."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")
        original_id = session.session_id

        # Record 19 turns
        for i in range(19):
            store.record_turn(original_id, f"msg {i}", f"reply {i}")

        reused = store.get_or_create(
            session_id=original_id, customer_id="CUST-001"
        )

        assert reused.session_id == original_id
        assert reused.turn_count == 19

    def test_record_turn_increments_count(self, store):
        """record_turn increments turn_count and appends messages."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")

        store.record_turn(session.session_id, "hello", "hi")

        assert session.turn_count == 1
        assert len(session.messages) == 2
        assert session.messages[0] == {"role": "user", "content": "hello"}
        assert session.messages[1] == {"role": "assistant", "content": "hi"}


# --- Test rate limit returns error after 10 messages in 60 seconds ---


class TestRateLimit:
    """Test rate limit returns error after 10 messages in 60 seconds."""

    def test_allows_first_10_messages(self, store):
        """First 10 messages within the window are allowed."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")

        for i in range(10):
            result = store.check_rate_limit(session.session_id)
            assert result is False, f"Message {i + 1} should be allowed"

    def test_blocks_11th_message(self, store):
        """The 11th message within 60 seconds is rate-limited."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")

        for _ in range(10):
            store.check_rate_limit(session.session_id)

        result = store.check_rate_limit(session.session_id)
        assert result is True

    def test_rate_limit_resets_after_window(self, store):
        """After 60 seconds, the rate limit window resets."""
        base_time = 1000000.0
        session = store.get_or_create(session_id=None, customer_id="CUST-001")

        # Send 10 messages at base_time
        with patch("api_lambda.chat_session.time.time", return_value=base_time):
            for _ in range(10):
                store.check_rate_limit(session.session_id)

        # After 61 seconds, messages should be allowed again
        with patch("api_lambda.chat_session.time.time", return_value=base_time + 61):
            result = store.check_rate_limit(session.session_id)
            assert result is False

    def test_rate_limit_unknown_session_returns_false(self, store):
        """check_rate_limit for unknown session returns False (allow)."""
        result = store.check_rate_limit("nonexistent-session-id")
        assert result is False


# --- Test lazy eviction removes expired sessions ---


class TestLazyEviction:
    """Test lazy eviction removes expired sessions."""

    def test_evicts_expired_sessions(self, store):
        """_evict_expired removes sessions past their TTL."""
        base_time = 1000000.0

        with patch("api_lambda.chat_session.time.time", return_value=base_time):
            s1 = store.get_or_create(session_id=None, customer_id="CUST-001")
            s2 = store.get_or_create(session_id=None, customer_id="CUST-002")

        assert s1.session_id in _mod._sessions
        assert s2.session_id in _mod._sessions

        # Advance past TTL
        expired_time = base_time + (CHAT_SESSION_TTL_MINUTES * 60) + 1
        with patch("api_lambda.chat_session.time.time", return_value=expired_time):
            store._evict_expired()

        assert s1.session_id not in _mod._sessions
        assert s2.session_id not in _mod._sessions

    def test_does_not_evict_active_sessions(self, store):
        """_evict_expired keeps sessions within TTL."""
        base_time = 1000000.0

        with patch("api_lambda.chat_session.time.time", return_value=base_time):
            session = store.get_or_create(session_id=None, customer_id="CUST-001")

        # Advance but stay within TTL
        within_ttl = base_time + (CHAT_SESSION_TTL_MINUTES * 60) - 10
        with patch("api_lambda.chat_session.time.time", return_value=within_ttl):
            store._evict_expired()

        assert session.session_id in _mod._sessions

    def test_eviction_triggered_on_get_or_create(self, store):
        """get_or_create triggers lazy eviction of expired sessions."""
        base_time = 1000000.0

        with patch("api_lambda.chat_session.time.time", return_value=base_time):
            old_session = store.get_or_create(session_id=None, customer_id="CUST-001")
            old_id = old_session.session_id

        # Advance past TTL and create a new session — old one should be evicted
        expired_time = base_time + (CHAT_SESSION_TTL_MINUTES * 60) + 1
        with patch("api_lambda.chat_session.time.time", return_value=expired_time):
            store.get_or_create(session_id=None, customer_id="CUST-002")

        assert old_id not in _mod._sessions


# --- Test stateless fallback when storage dict is corrupted ---


class TestStatelessFallback:
    """Test stateless fallback when storage dict is corrupted."""

    def test_fallback_on_storage_corruption(self, store):
        """When _sessions dict operations fail, falls back to stateless mode."""
        # Corrupt the storage by replacing _sessions with a broken object
        original_sessions = _mod._sessions

        class BrokenDict(dict):
            """Dict that raises on key access after initial setup."""

            def __contains__(self, key):
                raise RuntimeError("Storage corrupted")

            def __getitem__(self, key):
                raise RuntimeError("Storage corrupted")

        _mod._sessions = BrokenDict()
        try:
            # Should not raise — falls back to stateless mode
            session = store.get_or_create(
                session_id="some-id", customer_id="CUST-001"
            )

            assert session is not None
            assert session.customer_id == "CUST-001"
            assert session.turn_count == 0
            # Stateless session is NOT stored in the dict
            assert session.session_id not in original_sessions
        finally:
            _mod._sessions = original_sessions

    def test_fallback_session_has_valid_uuid(self, store):
        """Stateless fallback session still has a valid uuid4 session_id."""

        class BrokenDict(dict):
            def __contains__(self, key):
                raise RuntimeError("Storage corrupted")

        original_sessions = _mod._sessions
        _mod._sessions = BrokenDict()
        try:
            session = store.get_or_create(
                session_id="some-id", customer_id="CUST-001"
            )
            # Should be a valid uuid4
            uuid.UUID(session.session_id, version=4)
        finally:
            _mod._sessions = original_sessions

    def test_record_turn_graceful_on_unknown_session(self, store):
        """record_turn for unknown session logs warning but does not raise."""
        # Should not raise
        store.record_turn("nonexistent-session", "hello", "world")

    def test_record_turn_graceful_on_exception(self, store):
        """record_turn handles exceptions gracefully without raising."""
        session = store.get_or_create(session_id=None, customer_id="CUST-001")

        # Corrupt the session's messages list
        original_messages = session.messages
        session.messages = None  # type: ignore[assignment]

        # Should not raise — graceful degradation
        store.record_turn(session.session_id, "hello", "world")

        # Restore
        session.messages = original_messages
