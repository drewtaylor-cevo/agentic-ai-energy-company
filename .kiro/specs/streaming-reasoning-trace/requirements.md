# Requirements Document

## Introduction

Stream reasoning trace entries (tool calls and their deterministic summaries) to the UI in real time as the Strands agent executes, replacing the current batch-at-end delivery. The user sees progressive "agent thinking" steps ("Checking billing history… Detecting bill shock pattern… Computing TOU savings…") as each tool completes, making the 2–3 second agent latency feel responsive because the screen is alive. The final recommendation payload (green + cheapest tracks with narrative) still arrives as a single atomic response at the end — streaming applies only to the reasoning trace surface.

This feature builds on Strands SDK 1.37.0 streaming capabilities, API Gateway HTTP API v2 with Lambda Response Streaming (or WebSocket), and the existing `ReasoningTrace` React component which transitions from a `useEffect`-driven batch consumer to a Server-Sent Events (SSE) or streaming consumer.

All critical invariants are preserved: SAV-03 (LLM never does arithmetic), REC-03 (both tracks always returned), D-04 (never-500), D-11 (reasoning_trace summary exemption from narrative validators), D-15 (narrative dual-gate on usage_narrative and call_script), and the `_narrative_source` internal marker contract.

## Glossary

- **Streaming_API_Lambda**: The modified API Lambda (`api_lambda/handler.py`) that uses Lambda Response Streaming to send incremental reasoning trace events to the client before the final recommendation payload.
- **SSE_Stream**: A Server-Sent Events connection from the React UI to the Streaming_API_Lambda, carrying typed event frames (`trace_step`, `result`, `error`, `done`).
- **Trace_Step_Event**: A single SSE event of type `trace_step` containing one `ReasoningTraceEntry` (tool name + deterministic summary), emitted as each tool call completes inside the agent.
- **Result_Event**: A single SSE event of type `result` containing the final `RecommendationResponse` or `HardshipResponse` JSON payload, emitted after the agent turn completes.
- **Error_Event**: A single SSE event of type `error` containing an error message and HTTP-equivalent status code, emitted when the agent invocation fails.
- **Done_Event**: A terminal SSE event of type `done` with no data, signalling the client to close the connection.
- **Strands_Hook**: A Strands SDK `HookProvider` that subscribes to `AfterToolCallEvent` and emits `Trace_Step_Event` frames via a callback, using the same deterministic summary formatters from `agent/reasoning/summaries.py`.
- **Streaming_Callback**: A function injected into the agent hook that writes SSE-formatted bytes to the Lambda Response Streaming output channel.
- **ReasoningTrace_Component**: The existing React component (`ui/src/components/ReasoningTrace.tsx`) that renders the reasoning trace disclosure panel.
- **Batch_Fallback**: The existing non-streaming request path (`GET /recommendations/{customer_id}`) preserved for backward compatibility, returning the full response as a single JSON blob.
- **Wire_Protocol**: The SSE event framing format used between the Streaming_API_Lambda and the UI, consisting of typed events with JSON `data` payloads.
- **FourToolCapHook**: The existing Strands `HookProvider` that enforces the 4-tool-call budget per invocation.

## Requirements

### Requirement 1: Streaming API Endpoint

**User Story:** As a frontend developer, I want a streaming endpoint that sends reasoning trace steps incrementally, so that the UI can display agent progress in real time.

#### Acceptance Criteria

1. WHEN a client sends `GET /recommendations/{customer_id}` with an `Accept: text/event-stream` header, THE Streaming_API_Lambda SHALL respond with `Content-Type: text/event-stream` and stream SSE-formatted events.
2. WHEN a client sends `GET /recommendations/{customer_id}` without an `Accept: text/event-stream` header, THE Streaming_API_Lambda SHALL respond with the existing single-JSON-blob format (Batch_Fallback).
3. THE Streaming_API_Lambda SHALL validate `customer_id` against the `^CUST-\d{3,6}$` pattern before initiating a stream, returning a JSON error with HTTP 400 for invalid formats.
4. THE Streaming_API_Lambda SHALL generate a fresh `runtimeSessionId` (uuid4) inside the handler for each streaming invocation.

### Requirement 2: SSE Wire Protocol

**User Story:** As a frontend developer, I want a well-defined event protocol, so that I can parse streaming events reliably and handle each event type appropriately.

#### Acceptance Criteria

1. THE Wire_Protocol SHALL define exactly four event types: `trace_step`, `result`, `error`, and `done`.
2. WHEN a tool call completes during agent execution, THE Streaming_API_Lambda SHALL emit one `trace_step` event containing a JSON object with `tool` (string) and `summary` (string) fields matching the `ReasoningTraceEntry` schema.
3. WHEN the agent turn completes successfully, THE Streaming_API_Lambda SHALL emit one `result` event containing the full `RecommendationResponse` or `HardshipResponse` JSON payload (with `_narrative_source` stripped).
4. IF the agent invocation fails, THEN THE Streaming_API_Lambda SHALL emit one `error` event containing a JSON object with `status` (integer) and `message` (string) fields.
5. THE Streaming_API_Lambda SHALL emit exactly one `done` event as the final event in every stream, after either a `result` or `error` event.
6. WHEN a `trace_step` event is emitted, THE `summary` field SHALL be produced by the same deterministic formatters in `agent/reasoning/summaries.py` that produce the batch reasoning trace (SAV-03 compliance by construction).

### Requirement 3: Streaming Reasoning Trace Hook

**User Story:** As a backend developer, I want a Strands hook that emits trace events as tools complete, so that the streaming endpoint can forward them to the client without waiting for the full agent turn.

#### Acceptance Criteria

1. THE Strands_Hook SHALL implement the Strands `HookProvider` interface and subscribe to `AfterToolCallEvent`.
2. WHEN an `AfterToolCallEvent` fires for a tool in the set `{detect_bill_shock, get_billing_history, get_hardship_flag, simulate_savings}`, THE Strands_Hook SHALL invoke the Streaming_Callback with a formatted `Trace_Step_Event`.
3. WHEN an `AfterToolCallEvent` fires for a tool NOT in the known tool set, THE Strands_Hook SHALL skip the event without error.
4. THE Strands_Hook SHALL coexist with the existing FourToolCapHook on the same Agent instance without interfering with the tool-budget enforcement.
5. THE Strands_Hook SHALL use instance-level state (not module-level) and provide a `reset()` method called at the start of each invocation.

### Requirement 4: Invariant Preservation

**User Story:** As a system operator, I want streaming to preserve all existing correctness invariants, so that the demo remains trustworthy.

#### Acceptance Criteria

1. THE Streaming_API_Lambda SHALL strip the `_narrative_source` marker from the `result` event payload before emitting it to the client.
2. THE `result` event payload SHALL contain both `green` and `cheapest` tracks (REC-03) when the response kind is `recommendation`.
3. THE `trace_step` event summaries SHALL contain digits, currency symbols, percentages, and dates without any narrative filtering applied (D-11 exemption preserved).
4. THE Streaming_API_Lambda SHALL return a `done` event for every stream, including when the D-04 fallback path fires after an agent exception.
5. IF the agent invocation raises an exception, THEN THE Streaming_API_Lambda SHALL execute the existing D-04 fallback path and emit the fallback response as a `result` event followed by a `done` event.
6. THE Streaming_API_Lambda SHALL preserve the `?prewarm=1` path unchanged — prewarm requests SHALL return HTTP 204 with an empty body (no streaming).
7. THE Streaming_API_Lambda SHALL preserve the `?narrative=off` kill-switch — when active, `trace_step` events SHALL NOT be emitted, and the `result` event SHALL omit `reasoning_trace`, `compliance_review`, and `supervisor_trace` fields.

### Requirement 5: UI Streaming Consumer

**User Story:** As a call-centre operator, I want to see agent reasoning steps appear one by one as the agent works, so that the wait feels shorter and I can follow the agent's logic.

#### Acceptance Criteria

1. WHEN the UI initiates a recommendation lookup against a live backend, THE UI SHALL open an SSE connection to the streaming endpoint.
2. WHEN a `trace_step` event arrives, THE ReasoningTrace_Component SHALL append the new entry to the displayed trace list within one animation frame.
3. WHEN the `result` event arrives, THE UI SHALL render the recommendation cards (or hardship banner) using the final payload.
4. WHEN the `done` event arrives, THE UI SHALL close the SSE connection.
5. IF an `error` event arrives, THEN THE UI SHALL display the appropriate error state using the existing `ErrorAlert` component and close the connection.
6. WHILE the stream is open and no `result` event has arrived, THE UI SHALL display the `RecommendationSkeletons` loading state alongside any already-received trace steps.
7. WHEN the user submits a new customer ID while a stream is open, THE UI SHALL abort the in-flight SSE connection before opening a new one.

### Requirement 6: Mock Mode Compatibility

**User Story:** As a frontend developer, I want mock mode to simulate streaming behaviour, so that I can develop and test the UI without a deployed backend.

#### Acceptance Criteria

1. WHEN `VITE_API_URL` is unset or empty, THE UI SHALL simulate streaming by emitting mock `trace_step` events with a short delay between each, followed by the mock `result` event.
2. THE mock streaming simulation SHALL use the same `MOCK_RECOMMENDATIONS` and `MOCK_HARDSHIP_RESPONSES` fixtures as the existing batch mock path.
3. WHEN a mock lookup targets an unknown customer ID, THE UI SHALL emit a mock `error` event with status 404.

### Requirement 7: Backward Compatibility

**User Story:** As a system operator, I want the existing non-streaming API contract to remain functional, so that older clients or integration tests continue to work.

#### Acceptance Criteria

1. WHEN a client sends `GET /recommendations/{customer_id}` without an `Accept: text/event-stream` header, THE Streaming_API_Lambda SHALL return the identical JSON response format as the current implementation.
2. THE existing `GET /recommendations/{customer_id}/follow-up` endpoint SHALL remain unchanged and non-streaming.
3. THE Streaming_API_Lambda SHALL preserve the existing HTTP status code mapping: 400 for invalid customer ID, 404 for customer not found, 502 for service error, 504 for timeout.

### Requirement 8: Streaming Response Serialisation

**User Story:** As a backend developer, I want trace step events serialised correctly, so that the SSE parser on the client can reconstruct each event reliably.

#### Acceptance Criteria

1. THE Streaming_API_Lambda SHALL format each SSE event as `event: <type>\ndata: <json>\n\n` where `<type>` is one of the four Wire_Protocol event types and `<json>` is a single-line JSON string.
2. THE Streaming_API_Lambda SHALL flush each SSE event to the response stream immediately after formatting, without buffering multiple events.
3. THE `done` event SHALL be formatted as `event: done\ndata: {}\n\n`.
4. FOR ALL valid `ReasoningTraceEntry` objects, serialising to a `trace_step` SSE event and then parsing the SSE event back SHALL produce an equivalent `ReasoningTraceEntry` object (round-trip property).
