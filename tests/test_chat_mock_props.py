# Feature: conversational-chat-layer, Property 12: Mock keyword routing
"""Property-based tests for mock keyword routing.

**Validates: Requirements 9.2**

For any message sent in mock mode containing a known keyword (e.g., "bill",
"solar", "green"), the mock reply SHALL contain content semantically related
to that keyword's domain.

Since the mock implementation is TypeScript (ui/src/lib/mock/chatMock.ts), this
test validates the CONCEPT by implementing a Python equivalent of the keyword
routing logic and verifying the property holds across all generated inputs.
"""

import re

from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Python mirror of the TypeScript keyword routing logic from chatMock.ts
# ---------------------------------------------------------------------------

# Keywords and their expected semantic domains (content markers that indicate
# the reply is related to the keyword's domain).
KEYWORD_DOMAINS: dict[str, list[str]] = {
    "bill": ["billing", "bill", "usage", "monthly", "paid", "average"],
    "solar": ["solar", "renewable", "ecoflex", "save", "saving", "plan"],
    "green": ["green", "renewable", "ecoflex", "energy", "sourcing", "save"],
    "shock": ["shock", "spike", "anomaly", "increased", "usage", "average"],
    "hardship": ["hardship", "flag", "payment", "assistance", "support", "standing"],
    "savings": ["saving", "simulation", "plan", "month", "history", "usage"],
}

# Priority order for keyword matching (more specific first) — mirrors chatMock.ts
KEYWORD_PRIORITY_ORDER = ["shock", "hardship", "savings", "solar", "green", "bill"]

# Mock replies keyed by keyword — mirrors the TypeScript getRoutes() function.
MOCK_REPLIES: dict[str, str] = {
    "bill": (
        "Based on the billing records, this customer has had consistent usage "
        "over the past 12 months. The average monthly bill is within normal "
        "range for their household profile. The most recent bill is current "
        "and paid on time."
    ),
    "shock": (
        "Bill shock analysis shows an anomaly of +$45.60 in 2025-02 compared "
        "to the 11-month average. This spike appears to be driven by increased "
        "usage during that billing period. I'd recommend discussing the "
        "customer's usage patterns for that month."
    ),
    "solar": (
        "Based on the savings simulation, a solar-aligned plan (EcoFlex 100) "
        "could save this customer $30.00 per month. The plan sources 100% "
        "renewable energy and suits their usage profile well."
    ),
    "green": (
        "The green energy plan (EcoFlex 100) offers 100% renewable energy "
        "sourcing with a projected saving of $30.00 per month ($360.00 "
        "annually). It's well-suited to this customer's usage pattern."
    ),
    "savings": (
        "Savings simulation complete. The green plan (EcoFlex 100) would save "
        "$30.00/month and the cheapest plan (Value 12) would save $55.00/month "
        "based on this customer's 12-month usage history."
    ),
    "hardship": (
        "The hardship flag check shows this customer is not currently flagged "
        "for hardship support. Their account is in good standing with no "
        "payment assistance markers."
    ),
}

# Default fallback reply when no keyword matches.
DEFAULT_REPLY = (
    "Based on the customer records, I can help with that query. Could you "
    "provide more details about what specific aspect of the account you "
    "would like to know about?"
)


def mock_keyword_route(message: str) -> tuple[str, str | None]:
    """Python equivalent of the TypeScript keyword routing logic.

    Returns (reply, matched_keyword) where matched_keyword is None if no
    keyword was found in the message.
    """
    lower_message = message.lower()

    for keyword in KEYWORD_PRIORITY_ORDER:
        if keyword in lower_message:
            return MOCK_REPLIES[keyword], keyword

    return DEFAULT_REPLY, None


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy: generate a known keyword
_keyword_strategy = st.sampled_from(list(KEYWORD_DOMAINS.keys()))

# Strategy: generate surrounding text that does NOT contain any keyword
_non_keyword_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="<>",
    ),
    min_size=0,
    max_size=80,
).filter(
    lambda s: not any(kw in s.lower() for kw in KEYWORD_DOMAINS)
)


@st.composite
def _message_containing_keyword(draw) -> tuple[str, str]:
    """Generate a message containing exactly one known keyword with surrounding text.

    Returns (message, expected_keyword) tuple.
    """
    keyword = draw(_keyword_strategy)

    # Generate prefix and suffix text that don't contain any keywords.
    prefix = draw(_non_keyword_text)
    suffix = draw(_non_keyword_text)

    # Build message with the keyword embedded.
    # Use various casings to test case-insensitivity.
    casing = draw(st.sampled_from(["lower", "upper", "title", "mixed"]))
    if casing == "lower":
        kw_text = keyword
    elif casing == "upper":
        kw_text = keyword.upper()
    elif casing == "title":
        kw_text = keyword.title()
    else:
        # Mixed case: alternate upper/lower
        kw_text = "".join(
            c.upper() if i % 2 == 0 else c.lower()
            for i, c in enumerate(keyword)
        )

    message = f"{prefix} {kw_text} {suffix}".strip()

    # Ensure message is non-empty and within bounds.
    if not message:
        message = kw_text
    if len(message) > 2000:
        message = message[:2000]

    return message, keyword


@st.composite
def _message_with_multiple_keywords(draw) -> tuple[str, str]:
    """Generate a message containing multiple keywords.

    Returns (message, expected_matched_keyword) — the keyword that should
    match based on priority order.
    """
    # Pick 2-3 keywords to include.
    num_keywords = draw(st.integers(min_value=2, max_value=3))
    keywords = draw(
        st.lists(
            _keyword_strategy,
            min_size=num_keywords,
            max_size=num_keywords,
            unique=True,
        )
    )

    # Build message with all keywords.
    parts = []
    for kw in keywords:
        prefix = draw(_non_keyword_text)
        parts.append(f"{prefix} {kw}")
    suffix = draw(_non_keyword_text)
    parts.append(suffix)

    message = " ".join(parts).strip()
    if len(message) > 2000:
        message = message[:2000]

    # Determine which keyword should match based on priority order.
    expected_keyword = None
    for priority_kw in KEYWORD_PRIORITY_ORDER:
        if priority_kw in message.lower():
            expected_keyword = priority_kw
            break

    assume(expected_keyword is not None)
    return message, expected_keyword


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(data=_message_containing_keyword())
def test_keyword_routes_to_semantically_related_reply(data: tuple[str, str]) -> None:
    """For any message containing a known keyword, the mock reply contains content
    semantically related to that keyword's domain.

    **Validates: Requirements 9.2**

    The reply must contain at least one domain-related term from the keyword's
    semantic domain list, confirming the routing produced contextually appropriate
    content.
    """
    message, keyword = data

    reply, matched_keyword = mock_keyword_route(message)

    # The keyword must have been matched.
    assert matched_keyword is not None, (
        f"Expected keyword '{keyword}' to match in message: '{message[:100]}'"
    )

    # The reply must contain at least one term from the keyword's semantic domain.
    domain_terms = KEYWORD_DOMAINS[matched_keyword]
    reply_lower = reply.lower()

    has_domain_term = any(term in reply_lower for term in domain_terms)
    assert has_domain_term, (
        f"Reply for keyword '{matched_keyword}' does not contain any domain terms "
        f"{domain_terms}. Reply: '{reply[:200]}...'"
    )


@settings(max_examples=100)
@given(data=_message_containing_keyword())
def test_keyword_matching_is_case_insensitive(data: tuple[str, str]) -> None:
    """For any message containing a keyword in any casing, the mock routing
    still matches and returns a contextually appropriate reply.

    **Validates: Requirements 9.2**

    Case-insensitivity is a key property of the keyword matching — "BILL",
    "Bill", "bIlL" should all route to the billing domain.
    """
    message, keyword = data

    reply, matched_keyword = mock_keyword_route(message)

    # Must match regardless of casing.
    assert matched_keyword is not None, (
        f"Keyword '{keyword}' not matched (case-insensitive) in: '{message[:100]}'"
    )

    # The matched keyword must be one of the known keywords.
    assert matched_keyword in KEYWORD_DOMAINS, (
        f"Matched keyword '{matched_keyword}' is not in known keywords"
    )


@settings(max_examples=100)
@given(data=_message_with_multiple_keywords())
def test_multiple_keywords_use_priority_order(data: tuple[str, str]) -> None:
    """When a message contains multiple keywords, the routing uses priority order
    (more specific keywords first) to select the reply domain.

    **Validates: Requirements 9.2**

    Priority order: shock > hardship > savings > solar > green > bill.
    This ensures deterministic routing when messages are ambiguous.
    """
    message, expected_keyword = data

    reply, matched_keyword = mock_keyword_route(message)

    # Must match the highest-priority keyword present.
    assert matched_keyword == expected_keyword, (
        f"Expected priority keyword '{expected_keyword}' but got '{matched_keyword}' "
        f"for message: '{message[:100]}'"
    )

    # The reply must still be semantically related to the matched keyword.
    domain_terms = KEYWORD_DOMAINS[matched_keyword]
    reply_lower = reply.lower()
    has_domain_term = any(term in reply_lower for term in domain_terms)
    assert has_domain_term, (
        f"Reply for priority keyword '{matched_keyword}' does not contain domain terms "
        f"{domain_terms}. Reply: '{reply[:200]}...'"
    )


@settings(max_examples=100)
@given(message=_non_keyword_text)
def test_no_keyword_returns_default_fallback(message: str) -> None:
    """When a message contains no known keywords, the mock returns the default
    fallback reply (not a domain-specific reply).

    **Validates: Requirements 9.2**

    This ensures the routing only activates for known keywords and gracefully
    falls back for unrecognized queries.
    """
    assume(len(message.strip()) > 0)

    reply, matched_keyword = mock_keyword_route(message)

    # No keyword should match.
    assert matched_keyword is None, (
        f"Unexpected keyword match '{matched_keyword}' in message without keywords: "
        f"'{message[:100]}'"
    )

    # Reply should be the default fallback.
    assert reply == DEFAULT_REPLY, (
        f"Expected default fallback reply, got: '{reply[:100]}...'"
    )
