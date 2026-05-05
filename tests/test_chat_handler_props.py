# Feature: conversational-chat-layer, Property 1: Input validation rejects invalid requests
"""Property-based tests for chat handler input validation.

**Validates: Requirements 1.2, 1.3, 10.1, 10.2**

For any string that does not match `^CUST-\\d{3,6}$` as customer_id, OR any
message that is empty, whitespace-only, or exceeds 2000 characters, the chat
endpoint SHALL return HTTP 400 and never invoke the AgentCore runtime.
"""

import json
import re
from unittest.mock import patch, MagicMock

from botocore.exceptions import ClientError, ReadTimeoutError
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from api_lambda.chat_handler import chat_handler

# The valid customer_id pattern — used to generate INVALID IDs by exclusion.
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")


def _make_event(customer_id: str, message: str) -> dict:
    """Build a minimal Lambda proxy event for the chat handler."""
    return {
        "rawPath": f"/chat/{customer_id}",
        "pathParameters": {"customer_id": customer_id},
        "body": json.dumps({"message": message}),
        "headers": {"content-type": "application/json"},
    }


# Strategy: generate strings that do NOT match ^CUST-\d{3,6}$
# We combine several sub-strategies to cover diverse invalid formats.
_invalid_customer_id_strategy = st.one_of(
    # Empty string
    st.just(""),
    # Random text (no CUST- prefix)
    st.text(min_size=1, max_size=20).filter(lambda s: not _CUSTOMER_ID_PATTERN.match(s)),
    # CUST- prefix but wrong digit count (0, 1, 2, 7+ digits)
    st.from_regex(r"CUST-\d{0,2}", fullmatch=True),
    st.from_regex(r"CUST-\d{7,10}", fullmatch=True),
    # CUST- prefix with non-digit suffix
    st.from_regex(r"CUST-[a-zA-Z]{3,6}", fullmatch=True),
    # Close but wrong prefix
    st.from_regex(r"CUSTOMER-\d{3,6}", fullmatch=True),
    st.from_regex(r"cust-\d{3,6}", fullmatch=True),
    # Just digits
    st.from_regex(r"\d{3,6}", fullmatch=True),
)

# Strategy: generate invalid messages (empty, whitespace-only, or >2000 chars)
_invalid_message_strategy = st.one_of(
    # Empty string
    st.just(""),
    # Whitespace-only (spaces, tabs, newlines)
    st.from_regex(r"[\s]+", fullmatch=True).filter(lambda s: len(s) > 0 and not s.strip()),
    # Exceeds 2000 characters
    st.text(min_size=2001, max_size=2500).filter(lambda s: len(s) > 2000),
)

# Strategy: valid customer IDs (for testing invalid messages with valid customer_id)
_valid_customer_id_strategy = st.from_regex(r"CUST-\d{3,6}", fullmatch=True)

# Strategy: valid messages (for testing invalid customer_id with valid message)
_valid_message_strategy = st.text(min_size=1, max_size=100).filter(
    lambda s: s.strip() and len(s) <= 2000
)


@settings(max_examples=100)
@given(customer_id=_invalid_customer_id_strategy, message=_valid_message_strategy)
def test_invalid_customer_id_returns_400(customer_id: str, message: str) -> None:
    """Invalid customer_id format always returns HTTP 400 without invoking AgentCore.

    **Validates: Requirements 1.2, 10.1**
    """
    # Ensure the generated customer_id truly doesn't match the valid pattern.
    assume(not _CUSTOMER_ID_PATTERN.match(customer_id))

    event = _make_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client:
        result = chat_handler(event, None)

    # Must return 400.
    assert result["statusCode"] == 400, (
        f"Expected 400 for invalid customer_id '{customer_id}', got {result['statusCode']}"
    )

    # AgentCore must never be invoked.
    mock_client.invoke_agent_runtime.assert_not_called()


@settings(max_examples=100)
@given(customer_id=_valid_customer_id_strategy, message=_invalid_message_strategy)
def test_invalid_message_returns_400(customer_id: str, message: str) -> None:
    """Invalid message (empty, whitespace-only, or >2000 chars) returns HTTP 400 without invoking AgentCore.

    **Validates: Requirements 1.3, 10.1, 10.2**
    """
    event = _make_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client:
        with patch("api_lambda.chat_handler.session_store"):
            result = chat_handler(event, None)

    # Must return 400.
    assert result["statusCode"] == 400, (
        f"Expected 400 for invalid message (len={len(message)}, "
        f"stripped='{message.strip()[:20]}...'), got {result['statusCode']}"
    )

    # AgentCore must never be invoked.
    mock_client.invoke_agent_runtime.assert_not_called()


@settings(max_examples=100)
@given(
    customer_id=_invalid_customer_id_strategy,
    message=_invalid_message_strategy,
)
def test_both_invalid_returns_400(customer_id: str, message: str) -> None:
    """When both customer_id and message are invalid, returns HTTP 400 without invoking AgentCore.

    **Validates: Requirements 1.2, 1.3, 10.1, 10.2**
    """
    assume(not _CUSTOMER_ID_PATTERN.match(customer_id))

    event = _make_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client:
        result = chat_handler(event, None)

    # Must return 400.
    assert result["statusCode"] == 400, (
        f"Expected 400 for invalid customer_id '{customer_id}' and invalid message, "
        f"got {result['statusCode']}"
    )

    # AgentCore must never be invoked.
    mock_client.invoke_agent_runtime.assert_not_called()


# Feature: conversational-chat-layer, Property 2: Never-500 contract (D-04)
"""Property-based tests for the never-500 contract.

**Validates: Requirements 1.8, 8.2**

For any exception raised during chat processing (including unexpected RuntimeError,
TypeError, network failures, or any other exception type), the chat endpoint SHALL
return a non-500 HTTP status (502 for service errors, 504 for timeouts) and never
propagate an unhandled exception.
"""


# Strategy: generate various exception types that could occur during AgentCore invocation.
_general_exception_strategy = st.one_of(
    st.just(RuntimeError("unexpected runtime failure")),
    st.just(TypeError("'NoneType' object is not subscriptable")),
    st.just(ValueError("invalid literal for int()")),
    st.just(OSError("network unreachable")),
    st.just(IOError("broken pipe")),
    st.just(MemoryError("out of memory")),
    st.just(KeyError("missing_key")),
    st.just(AttributeError("object has no attribute 'foo'")),
    st.just(IndexError("list index out of range")),
    st.just(ConnectionError("connection refused")),
    st.just(TimeoutError("operation timed out")),
    st.just(PermissionError("access denied")),
    st.just(UnicodeDecodeError("utf-8", b"", 0, 1, "invalid start byte")),
    st.just(RecursionError("maximum recursion depth exceeded")),
    st.just(Exception("generic unexpected error")),
)


def _make_valid_chat_event(customer_id: str, message: str) -> dict:
    """Build a valid Lambda proxy event that passes input validation."""
    return {
        "rawPath": f"/chat/{customer_id}",
        "pathParameters": {"customer_id": customer_id},
        "body": json.dumps({"message": message}),
        "headers": {"content-type": "application/json"},
    }


def _make_mock_session():
    """Create a mock session object for patching session_store."""
    mock_session = MagicMock()
    mock_session.session_id = "test-session-id"
    mock_session.customer_id = "CUST-001"
    mock_session.messages = []
    return mock_session


@settings(max_examples=100)
@given(exception=_general_exception_strategy)
def test_never_500_on_general_exceptions(exception: Exception) -> None:
    """Any exception during AgentCore invocation returns non-500 status (502) and never raises.

    **Validates: Requirements 1.8, 8.2**
    """
    event = _make_valid_chat_event("CUST-001", "Why did her bill jump?")

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        # Configure session store to return a valid session.
        mock_store.get_or_create.return_value = _make_mock_session()
        mock_store.check_rate_limit.return_value = False

        # Configure AgentCore client to raise the generated exception.
        mock_client.invoke_agent_runtime.side_effect = exception

        # The handler must NEVER raise — it must always return a response dict.
        result = chat_handler(event, None)

    # Must never return 500.
    assert result["statusCode"] != 500, (
        f"Handler returned 500 for exception {type(exception).__name__}: {exception}"
    )
    # Must return 502 for general exceptions.
    assert result["statusCode"] == 502, (
        f"Expected 502 for {type(exception).__name__}, got {result['statusCode']}"
    )
    # Response must be valid JSON with an error field.
    body = json.loads(result["body"])
    assert "error" in body


@settings(max_examples=100)
@given(customer_id=_valid_customer_id_strategy, message=_valid_message_strategy)
def test_never_500_on_read_timeout(customer_id: str, message: str) -> None:
    """ReadTimeoutError during AgentCore invocation returns 504 (never 500) and never raises.

    **Validates: Requirements 1.8, 8.2**
    """
    event = _make_valid_chat_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        # Configure session store to return a valid session.
        mock_session = _make_mock_session()
        mock_session.customer_id = customer_id
        mock_store.get_or_create.return_value = mock_session
        mock_store.check_rate_limit.return_value = False

        # Configure AgentCore client to raise ReadTimeoutError.
        mock_client.invoke_agent_runtime.side_effect = ReadTimeoutError(endpoint_url="https://bedrock.us-east-1.amazonaws.com")

        # The handler must NEVER raise.
        result = chat_handler(event, None)

    # Must never return 500.
    assert result["statusCode"] != 500, (
        f"Handler returned 500 for ReadTimeoutError with customer_id={customer_id}"
    )
    # Must return 504 for timeout.
    assert result["statusCode"] == 504, (
        f"Expected 504 for ReadTimeoutError, got {result['statusCode']}"
    )
    # Response must be valid JSON with an error field.
    body = json.loads(result["body"])
    assert "error" in body


@settings(max_examples=100)
@given(customer_id=_valid_customer_id_strategy, message=_valid_message_strategy)
def test_never_500_on_client_error(customer_id: str, message: str) -> None:
    """ClientError during AgentCore invocation returns 502 (never 500) and never raises.

    **Validates: Requirements 1.8, 8.2**
    """
    event = _make_valid_chat_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        # Configure session store to return a valid session.
        mock_session = _make_mock_session()
        mock_session.customer_id = customer_id
        mock_store.get_or_create.return_value = mock_session
        mock_store.check_rate_limit.return_value = False

        # Configure AgentCore client to raise ClientError.
        mock_client.invoke_agent_runtime.side_effect = ClientError(
            error_response={"Error": {"Code": "ServiceUnavailableException", "Message": "Service unavailable"}},
            operation_name="InvokeAgentRuntime",
        )

        # The handler must NEVER raise.
        result = chat_handler(event, None)

    # Must never return 500.
    assert result["statusCode"] != 500, (
        f"Handler returned 500 for ClientError with customer_id={customer_id}"
    )
    # Must return 502 for service errors.
    assert result["statusCode"] == 502, (
        f"Expected 502 for ClientError, got {result['statusCode']}"
    )
    # Response must be valid JSON with an error field.
    body = json.loads(result["body"])
    assert "error" in body


# Feature: conversational-chat-layer, Property 4: Response schema completeness
"""Property-based tests for response schema completeness.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

For any successful chat response, the response SHALL contain all four required
fields: `reply` (non-empty string), `reasoning_trace` (array of `{tool: string,
summary: string}` objects), `session_id` (non-empty string), and `customer_id`
(string matching the request customer_id).
"""


# Strategy: generate varying AgentCore reply content.
_reply_strategy = st.text(min_size=1, max_size=500).filter(lambda s: s.strip())

# Strategy: generate reasoning trace entries (tool + summary pairs).
_tool_name_strategy = st.sampled_from([
    "simulate_savings",
    "detect_bill_shock",
    "get_billing_history",
    "get_hardship_flag",
])

_summary_strategy = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())

_reasoning_trace_entry_strategy = st.fixed_dictionaries({
    "tool": _tool_name_strategy,
    "summary": _summary_strategy,
})

_reasoning_trace_strategy = st.lists(
    _reasoning_trace_entry_strategy,
    min_size=0,
    max_size=4,
)


def _make_mock_agentcore_response(reply: str, reasoning_trace: list[dict]) -> MagicMock:
    """Create a mock AgentCore response with the given reply and trace."""
    response_body = json.dumps({
        "reply": reply,
        "reasoning_trace": reasoning_trace,
    }).encode()

    mock_response_stream = MagicMock()
    mock_response_stream.read.return_value = response_body

    mock_response = {"response": mock_response_stream}
    return mock_response


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_valid_message_strategy,
    reply=_reply_strategy,
    reasoning_trace=_reasoning_trace_strategy,
)
def test_response_schema_completeness(
    customer_id: str,
    message: str,
    reply: str,
    reasoning_trace: list[dict],
) -> None:
    """For any successful chat response, all four required fields are present with correct types.

    **Validates: Requirements 2.1, 2.2, 2.3, 2.4**

    Verifies:
    - `reply` is a non-empty string
    - `reasoning_trace` is an array of {tool: string, summary: string} objects
    - `session_id` is a non-empty string
    - `customer_id` matches the request customer_id
    """
    event = _make_valid_chat_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        # Configure session store to return a valid session.
        mock_session = _make_mock_session()
        mock_session.customer_id = customer_id
        mock_session.session_id = "sess-" + customer_id  # deterministic for assertion
        mock_store.get_or_create.return_value = mock_session
        mock_store.check_rate_limit.return_value = False

        # Configure AgentCore client to return a successful response.
        mock_client.invoke_agent_runtime.return_value = _make_mock_agentcore_response(
            reply, reasoning_trace
        )

        result = chat_handler(event, None)

    # Must return 200 for successful responses.
    assert result["statusCode"] == 200, (
        f"Expected 200 for valid request, got {result['statusCode']}: {result.get('body', '')}"
    )

    # Parse response body.
    body = json.loads(result["body"])

    # Requirement 2.1: reply field is a non-empty string.
    assert "reply" in body, "Response missing required field 'reply'"
    assert isinstance(body["reply"], str), (
        f"'reply' must be a string, got {type(body['reply']).__name__}"
    )
    assert body["reply"] == reply, (
        f"'reply' content mismatch: expected '{reply[:50]}...', got '{body['reply'][:50]}...'"
    )

    # Requirement 2.2: reasoning_trace is an array of {tool, summary} objects.
    assert "reasoning_trace" in body, "Response missing required field 'reasoning_trace'"
    assert isinstance(body["reasoning_trace"], list), (
        f"'reasoning_trace' must be a list, got {type(body['reasoning_trace']).__name__}"
    )
    for i, entry in enumerate(body["reasoning_trace"]):
        assert isinstance(entry, dict), (
            f"reasoning_trace[{i}] must be a dict, got {type(entry).__name__}"
        )
        assert "tool" in entry, f"reasoning_trace[{i}] missing 'tool' field"
        assert isinstance(entry["tool"], str), (
            f"reasoning_trace[{i}]['tool'] must be a string, got {type(entry['tool']).__name__}"
        )
        assert "summary" in entry, f"reasoning_trace[{i}] missing 'summary' field"
        assert isinstance(entry["summary"], str), (
            f"reasoning_trace[{i}]['summary'] must be a string, got {type(entry['summary']).__name__}"
        )

    # Requirement 2.3: session_id is a non-empty string.
    assert "session_id" in body, "Response missing required field 'session_id'"
    assert isinstance(body["session_id"], str), (
        f"'session_id' must be a string, got {type(body['session_id']).__name__}"
    )
    assert len(body["session_id"]) > 0, "'session_id' must be non-empty"

    # Requirement 2.4: customer_id matches the request customer_id.
    assert "customer_id" in body, "Response missing required field 'customer_id'"
    assert isinstance(body["customer_id"], str), (
        f"'customer_id' must be a string, got {type(body['customer_id']).__name__}"
    )
    assert body["customer_id"] == customer_id, (
        f"'customer_id' must match request: expected '{customer_id}', got '{body['customer_id']}'"
    )


# Feature: conversational-chat-layer, Property 11: HTML sanitization
"""Property-based tests for HTML sanitization.

**Validates: Requirements 10.5**

For any message containing HTML tags (e.g., <script>, <img>, <div>), the sanitized
message passed to the AgentCore runtime SHALL contain no HTML tags — all tags are
stripped before agent invocation.
"""


# Strategy: generate HTML tag names (common and dangerous).
_html_tag_names = st.sampled_from([
    "script", "img", "div", "span", "a", "p", "h1", "h2", "h3",
    "table", "tr", "td", "iframe", "object", "embed", "link",
    "style", "form", "input", "button", "textarea", "select",
    "svg", "math", "video", "audio", "source", "canvas",
    "b", "i", "u", "strong", "em", "br", "hr",
])

# Strategy: generate optional HTML attributes.
_html_attr_strategy = st.one_of(
    st.just(""),
    st.just(' class="foo"'),
    st.just(' id="bar"'),
    st.just(' src="http://evil.com/x.js"'),
    st.just(' onclick="alert(1)"'),
    st.just(' href="javascript:void(0)"'),
    st.just(' style="color:red"'),
    st.just(' onerror="fetch(\'http://evil.com\')"'),
)

# Strategy: generate text content around HTML tags.
_surrounding_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="<>"),
    min_size=0,
    max_size=50,
)


@st.composite
def _message_with_html_tags(draw):
    """Generate a message containing one or more HTML tags interspersed with text."""
    parts = []
    # Generate 1-5 HTML tag insertions.
    num_tags = draw(st.integers(min_value=1, max_value=5))
    for _ in range(num_tags):
        # Add some surrounding text before the tag.
        prefix = draw(_surrounding_text)
        if prefix:
            parts.append(prefix)

        # Generate an HTML tag (opening, self-closing, or with content).
        tag_name = draw(_html_tag_names)
        attrs = draw(_html_attr_strategy)
        tag_style = draw(st.sampled_from(["open_close", "self_closing", "open_only"]))

        if tag_style == "open_close":
            inner_text = draw(st.text(
                alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="<>"),
                min_size=0,
                max_size=20,
            ))
            parts.append(f"<{tag_name}{attrs}>{inner_text}</{tag_name}>")
        elif tag_style == "self_closing":
            parts.append(f"<{tag_name}{attrs}/>")
        else:
            parts.append(f"<{tag_name}{attrs}>")

    # Add trailing text.
    suffix = draw(_surrounding_text)
    if suffix:
        parts.append(suffix)

    message = "".join(parts)
    # Ensure the message is non-empty and within bounds.
    if not message.strip():
        message = "Hello <script>alert(1)</script> world"
    if len(message) > 2000:
        message = message[:2000]
    return message


@settings(max_examples=100)
@given(
    customer_id=_valid_customer_id_strategy,
    message=_message_with_html_tags(),
)
def test_html_sanitization_strips_all_tags(customer_id: str, message: str) -> None:
    """For any message containing HTML tags, the payload passed to AgentCore contains no HTML tags.

    **Validates: Requirements 10.5**

    The handler uses `re.sub(r'<[^>]+>', '', message)` for sanitization.
    We verify that the `message` field in the payload argument to `invoke_agent_runtime`
    contains no `<...>` patterns after sanitization.
    """
    event = _make_valid_chat_event(customer_id, message)

    with patch("api_lambda.chat_handler._chat_agentcore_client") as mock_client, \
         patch("api_lambda.chat_handler.session_store") as mock_store:
        # Configure session store to return a valid session.
        mock_session = _make_mock_session()
        mock_session.customer_id = customer_id
        mock_store.get_or_create.return_value = mock_session
        mock_store.check_rate_limit.return_value = False

        # Configure AgentCore client to return a successful response.
        mock_client.invoke_agent_runtime.return_value = _make_mock_agentcore_response(
            "Agent reply", [{"tool": "get_billing_history", "summary": "Retrieved data"}]
        )

        result = chat_handler(event, None)

    # The handler should succeed (200) since the message is valid after sanitization
    # (unless stripping all tags leaves an empty/whitespace-only string).
    if result["statusCode"] == 200:
        # Verify the payload passed to invoke_agent_runtime has no HTML tags.
        mock_client.invoke_agent_runtime.assert_called_once()
        call_kwargs = mock_client.invoke_agent_runtime.call_args
        # The payload is passed as a keyword argument (JSON-encoded bytes).
        payload_bytes = call_kwargs.kwargs.get("payload") or call_kwargs[1].get("payload")
        payload = json.loads(payload_bytes)

        sanitized_message = payload["message"]

        # The sanitized message must contain NO HTML tags (no <...> patterns).
        assert not re.search(r"<[^>]+>", sanitized_message), (
            f"HTML tags found in sanitized message passed to AgentCore: "
            f"'{sanitized_message[:100]}...' (original: '{message[:100]}...')"
        )
    else:
        # If the handler returned 400, it means the message after stripping tags
        # was empty/whitespace-only — that's acceptable behavior (validation catches it).
        assert result["statusCode"] == 400, (
            f"Expected 200 or 400, got {result['statusCode']} for message: '{message[:100]}...'"
        )
        # AgentCore must NOT have been invoked for invalid messages.
        mock_client.invoke_agent_runtime.assert_not_called()
