import { useCallback, useEffect, useRef, useState } from 'react';
import type { ChatMessage, ChatResponse, ReasoningTraceEntry } from '@/lib/types';
import { simulateChatStreaming } from '@/lib/mock/chatMock';

/**
 * Chat state machine for the conversational chat layer.
 *
 * State transitions:
 *   idle (isProcessing=false) → processing (isProcessing=true) on sendMessage
 *   processing → idle on chat_reply or error event
 *   Any → reset on customer change
 *
 * Requirements: 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
 */
export interface ChatState {
  messages: ChatMessage[];
  isProcessing: boolean;
  currentTrace: ReasoningTraceEntry[];
  sessionId: string | null;
  error: string | null;
}

const INITIAL_STATE: ChatState = {
  messages: [],
  isProcessing: false,
  currentTrace: [],
  sessionId: null,
  error: null,
};

/** Counter for generating unique message IDs when crypto.randomUUID is unavailable. */
let messageCounter = 0;

function generateMessageId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  messageCounter += 1;
  return `msg-${Date.now()}-${messageCounter}`;
}

/**
 * Parse a single SSE frame from a text chunk.
 * SSE format: `event: <type>\ndata: <json>\n\n`
 */
interface SSEEvent {
  event: string;
  data: string;
}

function parseSSEEvents(text: string): SSEEvent[] {
  const events: SSEEvent[] = [];
  const blocks = text.split('\n\n');

  for (const block of blocks) {
    if (!block.trim()) continue;

    let eventType = '';
    let data = '';

    const lines = block.split('\n');
    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith('data: ')) {
        data = line.slice(6);
      }
    }

    if (eventType && data) {
      events.push({ event: eventType, data });
    }
  }

  return events;
}

/**
 * Chat state management hook for the conversational chat layer.
 *
 * Manages the full chat lifecycle:
 * - Sends messages via POST to `/chat/{customer_id}` with SSE streaming
 * - Handles trace_step, chat_reply, error, and done events
 * - Stores session_id for multi-turn context
 * - Resets on customer change
 * - Falls back to mock mode when VITE_API_URL is unset
 *
 * Requirements: 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
 */
export function useChat(customerId: string) {
  const [state, setState] = useState<ChatState>(INITIAL_STATE);
  const abortRef = useRef<AbortController | (() => void) | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  // Reset on customer change (Requirement 6.7)
  useEffect(() => {
    // Abort any in-flight request
    if (abortRef.current) {
      if (abortRef.current instanceof AbortController) {
        abortRef.current.abort();
      } else {
        abortRef.current();
      }
      abortRef.current = null;
    }
    sessionIdRef.current = null;
    setState(INITIAL_STATE);
  }, [customerId]);

  const sendMessage = useCallback(async (message: string) => {
    const trimmed = message.trim();
    if (!trimmed) return;

    // Add user message to thread
    const userMessage: ChatMessage = {
      id: generateMessageId(),
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    };

    setState((prev) => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isProcessing: true,
      currentTrace: [],
      error: null,
    }));

    const apiUrl = import.meta.env.VITE_API_URL;

    if (!apiUrl) {
      // --- Mock mode (Requirement 9.1) ---
      // Cancel any in-flight mock simulation
      if (typeof abortRef.current === 'function') {
        abortRef.current();
      }

      let traceSteps: ReasoningTraceEntry[] = [];

      const abort = simulateChatStreaming(customerId, trimmed, {
        onTraceStep: (entry) => {
          traceSteps = [...traceSteps, entry];
          setState((prev) => ({
            ...prev,
            currentTrace: traceSteps,
          }));
        },
        onReply: (reply, reasoning_trace, session_id) => {
          sessionIdRef.current = session_id;
          const assistantMessage: ChatMessage = {
            id: generateMessageId(),
            role: 'assistant',
            content: reply,
            reasoning_trace,
            timestamp: Date.now(),
          };
          setState((prev) => ({
            ...prev,
            messages: [...prev.messages, assistantMessage],
            isProcessing: false,
            currentTrace: [],
            sessionId: session_id,
            error: null,
          }));
        },
        onError: (_status, errorMessage) => {
          setState((prev) => ({
            ...prev,
            isProcessing: false,
            currentTrace: [],
            error: errorMessage,
          }));
        },
        onDone: () => {
          // Stream complete — no additional state change needed
        },
      });

      abortRef.current = abort;
      return;
    }

    // --- Real API path: POST to /chat/{customer_id} with SSE ---
    // Cancel any in-flight request
    if (abortRef.current instanceof AbortController) {
      abortRef.current.abort();
    }

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    let traceSteps: ReasoningTraceEntry[] = [];

    try {
      const response = await fetch(
        `${apiUrl}/chat/${encodeURIComponent(customerId)}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          },
          body: JSON.stringify({
            message: trimmed,
            session_id: sessionIdRef.current ?? undefined,
          }),
          signal: ctrl.signal,
        },
      );

      if (!response.ok) {
        // Pre-stream error (validation, rate limit, etc.)
        let errorMessage = 'Chat service error. Please try again.';
        try {
          const errorBody = await response.json() as { error?: string };
          if (errorBody.error) {
            errorMessage = errorBody.error;
          }
        } catch {
          // Ignore JSON parse failure — use default message
        }
        setState((prev) => ({
          ...prev,
          isProcessing: false,
          currentTrace: [],
          error: errorMessage,
        }));
        return;
      }

      // Read SSE stream via ReadableStream
      const reader = response.body?.getReader();
      if (!reader) {
        setState((prev) => ({
          ...prev,
          isProcessing: false,
          error: 'Connection lost. Please try again.',
        }));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE frames (terminated by \n\n)
        const events = parseSSEEvents(buffer);
        // Keep any incomplete trailing data in the buffer
        const lastDoubleNewline = buffer.lastIndexOf('\n\n');
        if (lastDoubleNewline !== -1) {
          buffer = buffer.slice(lastDoubleNewline + 2);
        }

        for (const sseEvent of events) {
          switch (sseEvent.event) {
            case 'trace_step': {
              const entry: ReasoningTraceEntry = JSON.parse(sseEvent.data);
              traceSteps = [...traceSteps, entry];
              setState((prev) => ({
                ...prev,
                currentTrace: traceSteps,
              }));
              break;
            }
            case 'chat_reply': {
              const chatResponse: ChatResponse = JSON.parse(sseEvent.data);
              sessionIdRef.current = chatResponse.session_id;
              const assistantMessage: ChatMessage = {
                id: generateMessageId(),
                role: 'assistant',
                content: chatResponse.reply,
                reasoning_trace: chatResponse.reasoning_trace,
                timestamp: Date.now(),
              };
              setState((prev) => ({
                ...prev,
                messages: [...prev.messages, assistantMessage],
                isProcessing: false,
                currentTrace: [],
                sessionId: chatResponse.session_id,
                error: null,
              }));
              break;
            }
            case 'error': {
              const errorData = JSON.parse(sseEvent.data) as { status: number; message: string };
              setState((prev) => ({
                ...prev,
                isProcessing: false,
                currentTrace: [],
                error: errorData.message || 'Chat service error. Please try again.',
              }));
              break;
            }
            case 'done': {
              // Terminal event — stream is complete
              break;
            }
          }
        }
      }
    } catch (err: unknown) {
      // AbortError — request was superseded, ignore silently
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      // Network failure
      setState((prev) => ({
        ...prev,
        isProcessing: false,
        currentTrace: [],
        error: 'Connection lost. Please try again.',
      }));
    }
  }, [customerId]);

  const reset = useCallback(() => {
    // Abort any in-flight request
    if (abortRef.current) {
      if (abortRef.current instanceof AbortController) {
        abortRef.current.abort();
      } else {
        abortRef.current();
      }
      abortRef.current = null;
    }
    sessionIdRef.current = null;
    setState(INITIAL_STATE);
  }, []);

  return { state, sendMessage, reset } as const;
}
