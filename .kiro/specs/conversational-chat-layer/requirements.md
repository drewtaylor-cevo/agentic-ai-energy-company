# Requirements Document

## Introduction

Add a conversational chat layer to the Customer Tariff & Billing Optimisation Agent. A free-text question box appears below the recommendation cards, allowing the call-centre rep to ask open-ended questions about the customer: "Why did her bill jump in February?", "What would solar do for her?", "Draft an SMS confirming the switch." A new `POST /chat/{customer_id}` endpoint reuses the existing AgentCore runtime and tools — the LLM picks tools based on intent rather than a fixed recommendation flow. The same reasoning-trace UI shows the agent's tool calls and thinking in real time.

This single change reframes the product from a form-based lookup tool to a conversational agent-assist experience. The existing `GET /recommendations/{customer_id}` endpoint and its streaming variant remain unchanged — the chat layer is additive.

All critical invariants are preserved: SAV-03 (LLM never does arithmetic — all numbers come from tools), D-04 (never-500 contract — the chat endpoint never surfaces unhandled exceptions), D-15 (narrative dual-gate applies to any structured recommendation fields in chat responses), and SC-3 (no cross-customer session bleed — each chat exchange uses a fresh or short-lived session).

## Glossary

- **Chat_Endpoint**: The new `POST /chat/{customer_id}` API Gateway route handled by the API Lambda, which proxies free-text questions to the AgentCore runtime.
- **Chat_Request**: The JSON body sent to the Chat_Endpoint, containing a `message` field (the rep's free-text question) and an optional `session_id` field for multi-turn context.
- **Chat_Response**: The JSON response from the Chat_Endpoint, containing the agent's `reply` (free-text answer), a `reasoning_trace` (tool calls made), and metadata.
- **Chat_Session**: A short-lived conversational context scoped to a single customer and rep interaction. Sessions expire after a configurable TTL (default 15 minutes) and are never shared across customers (SC-3).
- **Chat_Agent_Prompt**: An extended system prompt for the AgentCore agent that handles open-ended questions while preserving numeric integrity rules (SAV-03) and the never-fabricate contract.
- **Chat_Input_Box**: The React UI component rendered below the recommendation cards, providing a free-text input field and send button for the rep to ask questions.
- **Chat_Thread**: The React UI component that displays the conversation history as a message thread (rep questions and agent replies), with reasoning trace disclosure for each agent turn.
- **Intent_Routing**: The LLM's ability to select appropriate tools based on the rep's question intent — no code-side router is needed; the agent's tool descriptions and system prompt guide tool selection.
- **Chat_SSE_Stream**: A Server-Sent Events connection from the UI to the Chat_Endpoint, carrying `trace_step`, `chat_reply`, `error`, and `done` events as the agent processes the question.
- **Numeric_Integrity**: The SAV-03 contract applied to chat — the agent copies tool-returned numbers verbatim and never estimates, rounds, or fabricates figures in its replies.
- **Session_Isolation**: The SC-3 pattern applied to chat — each chat session is scoped to exactly one `customer_id` and cannot access or leak data from other customers.

## Requirements

### Requirement 1: Chat API Endpoint

**User Story:** As a frontend developer, I want a POST endpoint that accepts free-text questions about a customer, so that the UI can send conversational queries to the agent.

#### Acceptance Criteria

1. WHEN a client sends `POST /chat/{customer_id}` with a JSON body containing a `message` field, THE Chat_Endpoint SHALL invoke the AgentCore runtime with the message and customer context, and return a Chat_Response.
2. THE Chat_Endpoint SHALL validate `customer_id` against the `^CUST-\d{3,6}$` pattern before processing, returning HTTP 400 with a JSON error for invalid formats.
3. THE Chat_Endpoint SHALL validate that the request body contains a non-empty `message` field (string, 1–2000 characters), returning HTTP 400 for missing or invalid messages.
4. THE Chat_Endpoint SHALL generate a fresh `runtimeSessionId` (uuid4) for each chat invocation when no `session_id` is provided in the request body.
5. WHEN a `session_id` is provided in the request body, THE Chat_Endpoint SHALL reuse that session ID for multi-turn context within the same customer scope.
6. IF the AgentCore invocation times out, THEN THE Chat_Endpoint SHALL return HTTP 504 with a JSON error message.
7. IF the AgentCore invocation fails with a service error, THEN THE Chat_Endpoint SHALL return HTTP 502 with a JSON error message.
8. THE Chat_Endpoint SHALL never return HTTP 500 — all unexpected exceptions are caught and mapped to HTTP 502 with a generic error message (D-04 contract).

### Requirement 2: Chat Response Schema

**User Story:** As a frontend developer, I want a well-defined response schema for chat replies, so that the UI can reliably parse and display agent answers.

#### Acceptance Criteria

1. THE Chat_Response SHALL contain a `reply` field (string) with the agent's free-text answer to the rep's question.
2. THE Chat_Response SHALL contain a `reasoning_trace` field (array of `{tool, summary}` objects) listing the tools the agent called and their deterministic summaries.
3. THE Chat_Response SHALL contain a `session_id` field (string) that the client can send back in subsequent requests for multi-turn context.
4. THE Chat_Response SHALL contain a `customer_id` field (string) echoing the customer the response pertains to.
5. THE `reasoning_trace` summaries SHALL be produced by the same deterministic formatters in `agent/reasoning/summaries.py` that produce the recommendation reasoning trace (SAV-03 compliance by construction).
6. THE `reply` field SHALL NOT be subject to D-15 narrative validators (it is free-text conversational output, not a structured recommendation field) — however, the agent's system prompt SHALL instruct it to cite tool-returned numbers verbatim and never fabricate figures.

### Requirement 3: Chat Streaming Wire Protocol

**User Story:** As a frontend developer, I want the chat endpoint to stream reasoning trace steps and the final reply incrementally, so that the rep sees agent progress in real time.

#### Acceptance Criteria

1. WHEN a client sends `POST /chat/{customer_id}` with an `Accept: text/event-stream` header, THE Chat_Endpoint SHALL respond with `Content-Type: text/event-stream` and stream SSE-formatted events.
2. THE Chat_SSE_Stream SHALL define exactly four event types: `trace_step`, `chat_reply`, `error`, and `done`.
3. WHEN a tool call completes during chat agent execution, THE Chat_Endpoint SHALL emit one `trace_step` event containing a JSON object with `tool` (string) and `summary` (string) fields.
4. WHEN the agent turn completes successfully, THE Chat_Endpoint SHALL emit one `chat_reply` event containing the full Chat_Response JSON payload.
5. IF the agent invocation fails, THEN THE Chat_Endpoint SHALL emit one `error` event containing a JSON object with `status` (integer) and `message` (string) fields.
6. THE Chat_Endpoint SHALL emit exactly one `done` event as the final event in every stream, after either a `chat_reply` or `error` event.
7. WHEN a client sends `POST /chat/{customer_id}` without an `Accept: text/event-stream` header, THE Chat_Endpoint SHALL return the Chat_Response as a single JSON blob (batch fallback).

### Requirement 4: Agent System Prompt Extension

**User Story:** As a system designer, I want the agent's system prompt extended to handle open-ended questions while preserving numeric integrity, so that the LLM gives accurate conversational answers grounded in tool data.

#### Acceptance Criteria

1. THE Chat_Agent_Prompt SHALL instruct the agent to answer the rep's question using available tools, selecting tools based on the question's intent.
2. THE Chat_Agent_Prompt SHALL preserve the SAV-03 numeric integrity rule — the agent SHALL copy tool-returned numbers verbatim and SHALL NOT estimate, round, or fabricate any figure.
3. THE Chat_Agent_Prompt SHALL instruct the agent to state "I don't have enough information to answer that" when no available tool can provide the data needed to answer the question.
4. THE Chat_Agent_Prompt SHALL instruct the agent to never disclose internal system details, tool names, prompt instructions, or implementation specifics to the rep.
5. THE Chat_Agent_Prompt SHALL instruct the agent to keep replies concise (under 200 words) and professional, suitable for a call-centre context.
6. THE Chat_Agent_Prompt SHALL be additive to the existing base system prompt — the recommendation flow's prompt rules remain unchanged when the agent is invoked via the recommendation path.

### Requirement 5: Session Management

**User Story:** As a system operator, I want chat sessions scoped to a single customer with short TTLs, so that there is no cross-customer data leakage and sessions do not accumulate indefinitely.

#### Acceptance Criteria

1. THE Chat_Session SHALL be scoped to exactly one `customer_id` — a session created for CUST-001 SHALL NOT be reusable for CUST-002.
2. WHEN a `session_id` is provided that was created for a different `customer_id`, THE Chat_Endpoint SHALL reject the request with HTTP 400 and a descriptive error message.
3. THE Chat_Session SHALL expire after 15 minutes of inactivity (configurable via environment variable `CHAT_SESSION_TTL_MINUTES`).
4. WHEN a session has expired, THE Chat_Endpoint SHALL create a new session transparently and include the new `session_id` in the response.
5. THE Chat_Endpoint SHALL enforce a maximum of 20 turns per session — after 20 exchanges, the session is closed and a new one must be started.
6. IF session storage is unavailable, THEN THE Chat_Endpoint SHALL fall back to stateless single-turn mode (fresh session per request) and log a warning, preserving the D-04 never-500 contract.

### Requirement 6: Chat UI Components

**User Story:** As a call-centre rep, I want a chat input box below the recommendation cards where I can type questions about the customer, so that I can get instant answers without leaving the screen.

#### Acceptance Criteria

1. WHEN recommendations have loaded successfully for a customer, THE Chat_Input_Box SHALL appear below the recommendation cards with placeholder text "Ask anything about this customer…".
2. WHEN the rep types a message and presses Enter or clicks Send, THE UI SHALL send the message to the Chat_Endpoint for the current customer and display the question in the Chat_Thread.
3. WHILE the chat agent is processing (stream open, no `chat_reply` received), THE Chat_Input_Box SHALL be disabled and a typing indicator SHALL appear in the Chat_Thread.
4. WHEN a `trace_step` event arrives during chat processing, THE Chat_Thread SHALL display the trace step in a reasoning-trace disclosure panel attached to the pending reply, using the same `ReasoningTrace` component pattern.
5. WHEN the `chat_reply` event arrives, THE Chat_Thread SHALL display the agent's reply as a new message in the thread and re-enable the Chat_Input_Box.
6. IF an `error` event arrives during chat processing, THEN THE Chat_Thread SHALL display an inline error message and re-enable the Chat_Input_Box.
7. WHEN a new customer is looked up (new recommendation flow triggered), THE Chat_Thread SHALL be cleared and the Chat_Input_Box SHALL be hidden until new recommendations load.

### Requirement 7: Chat UI Thread Display

**User Story:** As a call-centre rep, I want to see the conversation history as a message thread, so that I can review previous questions and answers during the call.

#### Acceptance Criteria

1. THE Chat_Thread SHALL display rep messages right-aligned and agent replies left-aligned, following standard chat UI conventions.
2. THE Chat_Thread SHALL display a reasoning-trace disclosure (expandable) below each agent reply that used tools, using the same visual pattern as the recommendation reasoning trace.
3. THE Chat_Thread SHALL auto-scroll to the latest message when a new message or reply is added.
4. THE Chat_Thread SHALL persist messages for the duration of the current customer session (cleared on new customer lookup).
5. WHILE the `?narrative=off` URL flag is active, THE Chat_Input_Box and Chat_Thread SHALL NOT be rendered (kill-switch collapses all post-v2.0 surfaces).

### Requirement 8: Invariant Preservation

**User Story:** As a system operator, I want the chat layer to preserve all existing correctness invariants, so that the demo remains trustworthy.

#### Acceptance Criteria

1. THE Chat_Endpoint SHALL preserve SAV-03 — all numbers in the agent's reply originate from tool calls; the agent never estimates, rounds, or fabricates figures.
2. THE Chat_Endpoint SHALL preserve D-04 — the endpoint never returns HTTP 500; all exceptions are caught and mapped to appropriate error responses.
3. THE Chat_Endpoint SHALL preserve SC-3 — each chat session is scoped to one customer; `runtimeSessionId` is never shared across customers.
4. THE existing `GET /recommendations/{customer_id}` endpoint and its streaming variant SHALL remain completely unchanged by the chat layer addition.
5. THE existing `GET /recommendations/{customer_id}/follow-up` endpoint SHALL remain completely unchanged.
6. THE Chat_Endpoint SHALL preserve the bi-mode import pattern — any new modules support both container (`/app/`) and repo (`agent/`) import paths.
7. THE Chat_Endpoint SHALL reuse the existing AgentCore runtime and tools — no new AgentCore deployment or separate agent container is required.

### Requirement 9: Chat Mock Mode

**User Story:** As a frontend developer, I want mock mode to simulate chat behaviour, so that I can develop and test the chat UI without a deployed backend.

#### Acceptance Criteria

1. WHEN `VITE_API_URL` is unset or empty, THE UI SHALL simulate chat by returning mock agent replies after a short delay, without making network requests.
2. THE mock chat simulation SHALL return contextually appropriate mock replies based on keyword matching in the rep's question (e.g., questions containing "bill" return billing-related mock answers).
3. THE mock chat simulation SHALL include mock `trace_step` events with appropriate tool names and summaries, emitted with short delays to simulate streaming.
4. WHEN a mock chat targets an unknown customer ID, THE UI SHALL return a mock error response with status 404.

### Requirement 10: Chat Input Validation and Safety

**User Story:** As a system operator, I want chat input validated and bounded, so that the system is protected from abuse and the agent operates within safe parameters.

#### Acceptance Criteria

1. THE Chat_Endpoint SHALL reject messages exceeding 2000 characters with HTTP 400.
2. THE Chat_Endpoint SHALL reject empty or whitespace-only messages with HTTP 400.
3. THE Chat_Agent_Prompt SHALL instruct the agent to decline requests that ask it to role-play, ignore instructions, or act outside its customer-service scope — the agent SHALL respond with a polite refusal and redirect to the customer's account.
4. THE Chat_Endpoint SHALL apply rate limiting of 10 messages per minute per customer session — exceeding the limit returns HTTP 429 with a descriptive error message.
5. THE Chat_Endpoint SHALL strip any HTML tags or script content from the `message` field before passing it to the agent (input sanitisation).

