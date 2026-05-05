# Implementation Plan: Streaming Reasoning Trace

## Overview

Replace the batch-at-end delivery of reasoning trace entries with real-time SSE streaming. The implementation touches four layers: a new Strands `StreamingTraceHook` (agent), SSE formatting + streaming handler (API Lambda), Lambda Function URL infrastructure (CDK), and an SSE consumer path in the React UI. The batch path remains completely unchanged as the canonical fallback.

## Tasks

- [x] 1. Create StreamingTraceHook and SSE formatter modules
  - [x] 1.1 Create `agent/hooks/streaming_trace.py` — StreamingTraceHook HookProvider
    - Implement `StreamingTraceHook` class with `HookProvider` interface
    - Subscribe to `AfterToolCallEvent` in `register_hooks()`
    - Filter tool names against `_TRACE_TOOLS` set (`detect_bill_shock`, `get_billing_history`, `get_hardship_flag`, `simulate_savings`)
    - Dispatch to deterministic summary formatters from `agent/reasoning/summaries.py`
    - Invoke injected `_callback(tool_name, summary)` for known tools; silently skip unknown tools
    - Implement `set_callback()` and `reset()` for per-invocation lifecycle (SC-3 pattern)
    - Use bi-mode imports matching `four_tool_cap.py` precedent
    - _Requirements: 3.1, 3.2, 3.3, 3.5_

  - [x] 1.2 Write property test for StreamingTraceHook — unknown tools silently skipped
    - **Property 6: Unknown tools are silently skipped**
    - **Validates: Requirements 3.3**

  - [x] 1.3 Write property test for StreamingTraceHook — summary integrity
    - **Property 5: Summary integrity — deterministic formatters, no narrative filtering**
    - **Validates: Requirements 2.6, 4.3**

  - [x] 1.4 Create `api_lambda/sse.py` — pure SSE formatting functions
    - Implement `format_sse_event(event_type, data)` returning `event: <type>\ndata: <json>\n\n`
    - Implement `format_done_event()` returning `event: done\ndata: {}\n\n`
    - Use `json.dumps(data, separators=(",", ":"))` for single-line compact JSON
    - _Requirements: 8.1, 8.3_

  - [x] 1.5 Write property test for SSE framing format
    - **Property 8: SSE framing format**
    - **Validates: Requirements 8.1**

  - [x] 1.6 Write property test for ReasoningTraceEntry round-trip serialisation
    - **Property 9: ReasoningTraceEntry round-trip serialisation**
    - **Validates: Requirements 8.4**

- [x] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Add streaming handler to API Lambda
  - [x] 3.1 Add streaming code path to `api_lambda/handler.py`
    - Add content negotiation: check `Accept: text/event-stream` header
    - When SSE requested, delegate to new `_stream_handler()` function
    - When SSE not requested, fall through to existing `handler()` unchanged (Requirement 7.1)
    - Implement `_stream_handler()` with Lambda Response Streaming write pattern
    - Validate `customer_id` against `^CUST-\d{3,6}$` before opening stream (return JSON 400 on invalid)
    - Handle `?prewarm=1` — return 204 with empty body, no streaming (Requirement 4.6)
    - Handle `?narrative=off` — suppress `trace_step` events, strip reasoning_trace/compliance_review/supervisor_trace from result (Requirement 4.7)
    - Generate fresh `runtimeSessionId` (uuid4) inside handler per invocation
    - Wire `StreamingTraceHook.set_callback()` to write SSE frames to response stream
    - Invoke AgentCore, emit `trace_step` events as tools complete
    - On success: strip `_narrative_source`, emit `result` event, emit `done` event
    - On exception: execute D-04 fallback, emit fallback as `result` event + `done` event
    - On customer not found: emit `error` event (404) + `done` event
    - Preserve existing follow-up endpoint unchanged (Requirement 7.2)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 4.1, 4.4, 4.5, 4.6, 4.7, 7.1, 7.2, 7.3, 8.2_

  - [x] 3.2 Write property test for customer ID validation in streaming path
    - **Property 1: Customer ID validation rejects all non-matching inputs**
    - **Validates: Requirements 1.3**

  - [x] 3.3 Write property test for session ID uniqueness
    - **Property 2: Session ID uniqueness across invocations**
    - **Validates: Requirements 1.4**

  - [x] 3.4 Write property test for _narrative_source stripping
    - **Property 3: _narrative_source is never exposed to the client**
    - **Validates: Requirements 2.3, 4.1**

  - [x] 3.5 Write property test for done event termination
    - **Property 4: Every stream terminates with exactly one done event**
    - **Validates: Requirements 2.5, 4.4**

  - [x] 3.6 Write property test for REC-03 in streaming result events
    - **Property 7: REC-03 preserved in streaming result events**
    - **Validates: Requirements 4.2**

  - [x] 3.7 Write unit tests for streaming handler
    - Test content negotiation routing (Accept header present vs absent)
    - Test prewarm bypass returns 204 regardless of Accept header
    - Test `?narrative=off` suppresses trace_step events
    - Test D-04 fallback emits result + done (not error)
    - Test error event shape for each error scenario (400, 404, 502, 504)
    - Test follow-up endpoint ignores Accept header (always JSON)
    - _Requirements: 1.1, 1.2, 4.5, 4.6, 4.7, 7.2, 7.3_

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Add Lambda Function URL infrastructure
  - [x] 5.1 Update `infrastructure/constructs/backend_api.py` — add Function URL with response streaming
    - Add `fn.add_function_url()` with `invoke_mode=lambda_.InvokeMode.RESPONSE_STREAM`
    - Configure `auth_type=lambda_.FunctionUrlAuthType.NONE`
    - Configure CORS: `allowed_origins=["*"]`, `allowed_methods=[HttpMethod.GET]`, `allowed_headers=["Content-Type", "Accept"]`
    - Write Function URL endpoint to SSM parameter (`/customer-tariff/streaming-url`)
    - Add `CfnOutput` for the streaming URL in `infrastructure/backend_api_stack.py`
    - _Requirements: 1.1_

  - [x] 5.2 Write unit tests for CDK construct changes
    - Test Function URL is created with RESPONSE_STREAM invoke mode
    - Test CORS configuration on Function URL
    - Test SSM parameter is written
    - _Requirements: 1.1_

- [x] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement UI streaming consumer and mock simulation
  - [x] 7.1 Add SSE event types to `ui/src/lib/types.ts`
    - Add `TraceStepEvent` interface (`tool: string`, `summary: string`)
    - Add `StreamingErrorEvent` interface (`status: number`, `message: string`)
    - _Requirements: 2.1_

  - [x] 7.2 Create `ui/src/lib/mock/streamingMock.ts` — mock streaming simulation
    - Implement `simulateStreaming()` that emits mock `trace_step` events with ~300ms delay between each
    - Use `MOCK_REASONING_TRACE_CUST003` fixture for CUST-003; empty trace for other known personas
    - Emit mock `result` event from `MOCK_RECOMMENDATIONS` or `MOCK_HARDSHIP_RESPONSES`
    - For unknown customer IDs, emit mock `error` event with status 404
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 7.3 Create `ui/src/hooks/useStreamingRecommendations.ts` — SSE consumer hook
    - Implement `StreamingState` type with statuses: `idle`, `streaming`, `success`, `hardship`, `error`
    - Include `traceSteps: ReasoningTraceEntry[]` in state for progressive append
    - Use `EventSource` for SSE connection to `VITE_STREAMING_URL`
    - On `trace_step` event: append to `traceSteps` array
    - On `result` event: transition to `success` or `hardship` state
    - On `done` event: close `EventSource`
    - On `error` event: transition to error state, close connection
    - On new lookup: abort in-flight `EventSource` before opening new one
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.7_

  - [x] 7.4 Update `ui/src/hooks/useRecommendations.ts` — integrate streaming path
    - When `VITE_STREAMING_URL` is set, delegate to `useStreamingRecommendations`
    - When `VITE_API_URL` is unset and `VITE_STREAMING_URL` is unset, use mock streaming simulation
    - When only `VITE_API_URL` is set, preserve existing batch fetch path as fallback
    - Expose `traceSteps` from streaming state for progressive rendering
    - _Requirements: 5.1, 6.1, 7.1_

  - [x] 7.5 Update `ui/src/components/ReasoningTrace.tsx` — progressive rendering
    - Accept trace entries that grow incrementally during streaming
    - Render new entries as they arrive (within one animation frame)
    - Show skeletons + already-received trace steps while streaming
    - Preserve existing collapsed/expanded disclosure behavior
    - Preserve LD-7 kill-switch (`?narrative=off` renders null)
    - _Requirements: 5.2, 5.6_

  - [x] 7.6 Write vitest tests for streaming UI components
    - Test `useStreamingRecommendations` hook: trace_step appends, result transitions, done closes
    - Test `useRecommendations` delegates to SSE when `VITE_STREAMING_URL` is set
    - Test abort on re-query closes existing EventSource
    - Test mock streaming simulation emits events with delays
    - Test mock unknown customer ID emits 404 error
    - Test `ReasoningTrace` component renders progressive entries
    - Test skeletons + trace steps visible during streaming state
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.7, 6.1, 6.2, 6.3_

- [x] 8. Wire StreamingTraceHook into agent
  - [x] 8.1 Update `agent/agent.py` — register StreamingTraceHook alongside FourToolCapHook
    - Add bi-mode import for `StreamingTraceHook` (same pattern as `FourToolCapHook`)
    - Instantiate `_streaming_trace_hook = StreamingTraceHook()` at module level
    - Add to `Agent(hooks=[_four_tool_cap, _streaming_trace_hook])`
    - Call `_streaming_trace_hook.reset()` at the top of `invoke()` (alongside `_four_tool_cap.reset()`)
    - _Requirements: 3.1, 3.4, 3.5_

  - [x] 8.2 Write unit tests for hook coexistence
    - Test both hooks register for `AfterToolCallEvent` independently
    - Test `StreamingTraceHook.reset()` clears callback
    - Test `FourToolCapHook` budget enforcement is unaffected by `StreamingTraceHook` presence
    - _Requirements: 3.4_

- [x] 9. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 9 universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The batch path (`handler()`) is never modified — streaming is additive only
- All critical invariants preserved: SAV-03, REC-03, D-04, D-11, D-15, `_narrative_source` stripping
- Bi-mode imports follow the established `four_tool_cap.py` / `narrative/` precedent
- D-22: Strands 1.37.0 pinned — no SDK changes required
