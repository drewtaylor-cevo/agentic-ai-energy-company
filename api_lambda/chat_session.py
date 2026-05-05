"""In-memory chat session store with TTL, turn-cap, and rate limiting.

Provides lightweight session management for the conversational chat layer.
Sessions are stored in a module-level dict (shared across warm Lambda
invocations). Expired sessions are lazily evicted on access.

Design decisions:
- In-memory storage is acceptable for demo scope (15-min TTL, 20-turn cap,
  single Lambda instance).
- Graceful degradation: if storage operations fail, fall back to stateless
  mode (fresh session per request) and log a warning (D-04 contract).
- Cross-customer rejection: a session created for CUST-A rejects CUST-B
  with ValueError (SC-3 session isolation).
- Rate limiting: 10 messages per minute per session, tracked via timestamps.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.4
"""

import logging
import os
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Configurable TTL via environment variable (default 15 minutes).
CHAT_SESSION_TTL_MINUTES = int(os.environ.get("CHAT_SESSION_TTL_MINUTES", "15"))

# Hard limits.
_MAX_TURNS = 20
_RATE_LIMIT_MESSAGES = 10
_RATE_LIMIT_WINDOW_SECONDS = 60


@dataclass
class ChatSession:
    """A single chat session scoped to one customer."""

    session_id: str
    customer_id: str
    created_at: float
    last_active: float
    turn_count: int
    messages: list[dict] = field(default_factory=list)
    # Rate limiting: timestamps of messages within the current window.
    _message_timestamps: list[float] = field(default_factory=list, repr=False)


# Module-level storage — shared across warm Lambda invocations.
_sessions: dict[str, ChatSession] = {}


class ChatSessionStore:
    """In-memory session store with TTL and turn-cap enforcement.

    Uses the module-level `_sessions` dict for storage. Provides graceful
    degradation to stateless mode if storage operations fail unexpectedly.
    """

    def get_or_create(self, session_id: str | None, customer_id: str) -> ChatSession:
        """Resolve or create a session for the given customer.

        Args:
            session_id: Existing session ID to reuse, or None for a new session.
            customer_id: The customer this session belongs to.

        Returns:
            A valid ChatSession (existing or newly created).

        Raises:
            ValueError: If session_id belongs to a different customer (SC-3).
        """
        try:
            self._evict_expired()
        except Exception:  # pragma: no cover
            logger.warning("Session eviction failed — continuing with stale store")

        try:
            if session_id and session_id in _sessions:
                session = _sessions[session_id]

                # SC-3: Cross-customer rejection.
                if session.customer_id != customer_id:
                    raise ValueError(
                        f"Session belongs to a different customer."
                    )

                # TTL check: if expired, create a new session transparently.
                ttl_seconds = CHAT_SESSION_TTL_MINUTES * 60
                if (time.time() - session.last_active) > ttl_seconds:
                    logger.info(
                        "Session %s expired — creating new session for %s",
                        session_id, customer_id,
                    )
                    del _sessions[session_id]
                    return self._create_session(customer_id)

                # Turn cap: if at or beyond 20 turns, close and create new.
                if session.turn_count >= _MAX_TURNS:
                    logger.info(
                        "Session %s reached turn cap (%d) — creating new session for %s",
                        session_id, session.turn_count, customer_id,
                    )
                    del _sessions[session_id]
                    return self._create_session(customer_id)

                # Valid session — update last_active and return.
                session.last_active = time.time()
                return session

            # No existing session or session_id not found — create new.
            return self._create_session(customer_id)

        except ValueError:
            # Re-raise ValueError (cross-customer rejection) — not a storage failure.
            raise
        except Exception as exc:
            # Graceful degradation (D-04): fall back to stateless mode.
            logger.warning(
                "Session storage error — falling back to stateless mode: %s", exc
            )
            return self._create_stateless_session(customer_id)

    def record_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """Append a turn to the session history and increment the counter.

        Args:
            session_id: The session to record the turn in.
            user_msg: The user's message.
            assistant_msg: The assistant's reply.
        """
        try:
            if session_id not in _sessions:
                logger.warning("record_turn called for unknown session %s", session_id)
                return

            session = _sessions[session_id]
            session.messages.append({"role": "user", "content": user_msg})
            session.messages.append({"role": "assistant", "content": assistant_msg})
            session.turn_count += 1
            session.last_active = time.time()
        except Exception as exc:
            # Graceful degradation: log and continue — don't break the response.
            logger.warning("record_turn failed for session %s: %s", session_id, exc)

    def check_rate_limit(self, session_id: str) -> bool:
        """Check if the session has exceeded the rate limit.

        Args:
            session_id: The session to check.

        Returns:
            True if rate limit is exceeded (caller should reject), False if OK.
        """
        try:
            if session_id not in _sessions:
                return False

            session = _sessions[session_id]
            now = time.time()
            cutoff = now - _RATE_LIMIT_WINDOW_SECONDS

            # Prune old timestamps outside the window.
            session._message_timestamps = [
                ts for ts in session._message_timestamps if ts > cutoff
            ]

            # Check if at or over the limit.
            if len(session._message_timestamps) >= _RATE_LIMIT_MESSAGES:
                return True

            # Record this message timestamp.
            session._message_timestamps.append(now)
            return False

        except Exception as exc:
            # Graceful degradation: if rate check fails, allow the message.
            logger.warning("Rate limit check failed for session %s: %s", session_id, exc)
            return False

    def _evict_expired(self) -> None:
        """Lazy eviction of expired sessions on access."""
        now = time.time()
        ttl_seconds = CHAT_SESSION_TTL_MINUTES * 60
        expired_ids = [
            sid for sid, session in _sessions.items()
            if (now - session.last_active) > ttl_seconds
        ]
        for sid in expired_ids:
            del _sessions[sid]
        if expired_ids:
            logger.info("Evicted %d expired session(s)", len(expired_ids))

    def _create_session(self, customer_id: str) -> ChatSession:
        """Create a new session and store it."""
        now = time.time()
        session = ChatSession(
            session_id=str(uuid.uuid4()),
            customer_id=customer_id,
            created_at=now,
            last_active=now,
            turn_count=0,
            messages=[],
        )
        _sessions[session.session_id] = session
        return session

    def _create_stateless_session(self, customer_id: str) -> ChatSession:
        """Create a session that is NOT stored — stateless fallback."""
        now = time.time()
        return ChatSession(
            session_id=str(uuid.uuid4()),
            customer_id=customer_id,
            created_at=now,
            last_active=now,
            turn_count=0,
            messages=[],
        )


# Module-level singleton for use by the chat handler.
session_store = ChatSessionStore()
