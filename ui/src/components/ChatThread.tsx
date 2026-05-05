// Conversational chat layer — ChatThread component.
// Displays the conversation history as a message thread:
// - Rep messages (role='user') right-aligned
// - Agent replies (role='assistant') left-aligned
// - Reasoning trace disclosure below agent replies that used tools
// - Auto-scroll to latest message
// - Typing indicator during processing
// - Inline error message display (not modal)
// Requirements: 6.3, 6.4, 6.5, 6.6, 7.1, 7.2, 7.3, 7.4
import { useEffect, useRef } from 'react';
import { ReasoningTrace } from '@/components/ReasoningTrace';
import type { ChatMessage, ReasoningTraceEntry } from '@/lib/types';

interface ChatThreadProps {
  messages: ChatMessage[];
  isProcessing: boolean;
  currentTrace: ReasoningTraceEntry[];
  error: string | null;
}

export function ChatThread({ messages, isProcessing, currentTrace, error }: ChatThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message when messages change or processing state updates.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing, error]);

  if (messages.length === 0 && !isProcessing && !error) return null;

  return (
    <section className="mt-4 max-h-96 overflow-y-auto space-y-3" aria-label="Chat thread">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
              msg.role === 'user'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-foreground'
            }`}
          >
            <p className="whitespace-pre-wrap">{msg.content}</p>
            {/* Reasoning trace disclosure for agent replies that used tools */}
            {msg.role === 'assistant' && msg.reasoning_trace && msg.reasoning_trace.length > 0 && (
              <div className="mt-2 border-t border-border pt-2">
                <ReasoningTrace trace={msg.reasoning_trace} />
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Typing indicator during processing */}
      {isProcessing && (
        <div className="flex justify-start">
          <div className="bg-muted rounded-lg px-3 py-2">
            {/* Show live reasoning trace while processing */}
            {currentTrace.length > 0 && (
              <div className="mb-2">
                <ReasoningTrace trace={currentTrace} isStreaming />
              </div>
            )}
            <div
              className="flex items-center gap-1"
              aria-label="Agent is typing"
              data-testid="typing-indicator"
            >
              <span className="size-2 rounded-full bg-muted-foreground animate-pulse" />
              <span className="size-2 rounded-full bg-muted-foreground animate-pulse [animation-delay:150ms]" />
              <span className="size-2 rounded-full bg-muted-foreground animate-pulse [animation-delay:300ms]" />
            </div>
          </div>
        </div>
      )}

      {/* Inline error message display */}
      {error && (
        <div
          className="flex justify-start"
          role="alert"
          data-testid="chat-error"
        >
          <p className="text-sm text-destructive px-3 py-2">
            {error}
          </p>
        </div>
      )}

      {/* Scroll anchor */}
      <div ref={bottomRef} />
    </section>
  );
}
